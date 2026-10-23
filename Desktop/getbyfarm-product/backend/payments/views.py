import hmac
import logging

from django.conf import settings
from django.db import IntegrityError
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from .models import Payment
from .mpesa_adapter import MockMpesaAdapter, PaymentError, get_payment_adapter, normalize_msisdn
from .services import amount_to_charge, apply_payment_result

logger = logging.getLogger(__name__)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "order", "provider", "provider_reference", "amount", "status", "result_description", "created_at"]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    phone_number = serializers.CharField(max_length=20)


class InitiatePaymentView(APIView):
    """POST /api/payments/initiate/ — start an M-Pesa STK push for a submitted, unpaid order."""
    throttle_scope = "payment"

    def post(self, request):
        ser = InitiatePaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        order = Order.objects.filter(pk=ser.validated_data["order_id"], branch_id=request.user.branch_id).first()
        if order is None:  # same answer for "doesn't exist" and "not yours": don't leak existence
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        if order.status != "submitted":
            msg = ("This order is waiting for approval before it can be paid."
                   if order.status == "draft" else f"This order can't be paid (status: {order.status}).")
            return Response({"detail": msg}, status=status.HTTP_409_CONFLICT)

        try:
            phone = normalize_msisdn(ser.validated_data["phone_number"])
            adapter = get_payment_adapter(settings)
        except PaymentError as exc:
            return Response({"detail": exc.user_message}, status=status.HTTP_400_BAD_REQUEST)

        amount = amount_to_charge(order)
        try:
            payment = Payment.objects.create(order=order, provider="mpesa", amount=amount)
        except IntegrityError:  # unique constraint: a pending/successful payment already exists
            return Response({"detail": "A payment is already in progress or completed for this order."},
                            status=status.HTTP_409_CONFLICT)

        cfg = settings.MPESA_CONFIG
        callback_url = f"{cfg['CALLBACK_BASE_URL'].rstrip('/')}/api/payments/mpesa-callback/{cfg['CALLBACK_SECRET']}/"
        if not isinstance(adapter, MockMpesaAdapter) and (not cfg["CALLBACK_BASE_URL"] or not cfg["CALLBACK_SECRET"]):
            payment.status, payment.result_description = "failed", "Callback URL not configured"
            payment.save(update_fields=["status", "result_description", "updated_at"])
            logger.error("MPESA_CALLBACK_BASE_URL / MPESA_CALLBACK_SECRET not set; cannot take payments")
            return Response({"detail": "Payments are temporarily unavailable."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            result = adapter.initiate(phone=phone, amount=int(amount), account_reference=order.order_number,
                                      callback_url=callback_url)
        except PaymentError as exc:
            payment.status, payment.result_description = "failed", str(exc)[:255]
            payment.save(update_fields=["status", "result_description", "updated_at"])
            return Response({"detail": exc.user_message}, status=status.HTTP_502_BAD_GATEWAY)

        payment.provider_reference = result.checkout_request_id
        payment.save(update_fields=["provider_reference", "updated_at"])

        if isinstance(adapter, MockMpesaAdapter):  # demo/staging only: settle inline, there is no callback
            payment = apply_payment_result(payment.id, success=True, receipt=f"MOCK{payment.id.hex[:8].upper()}",
                                           paid_amount=amount, description=result.message)

        return Response({"payment": PaymentSerializer(payment).data, "message": result.message},
                        status=status.HTTP_202_ACCEPTED)


class PaymentStatusView(APIView):
    """GET /api/payments/status/<order_id>/ — the frontend polls this while the buyer enters their PIN."""

    def get(self, request, order_id):
        payment = (Payment.objects.filter(order_id=order_id, order__branch_id=request.user.branch_id)
                   .order_by("-created_at").first())
        if payment is None:
            return Response({"detail": "No payment for this order."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PaymentSerializer(payment).data)


class MpesaCallbackView(APIView):
    """
    POST /api/payments/mpesa-callback/<secret>/ — called by Safaricom, not by browsers.

    Daraja does not sign callbacks, so we defend in layers: (1) the URL contains an unguessable secret,
    (2) the CheckoutRequestID must match a pending payment WE created, (3) amounts must match,
    (4) processing is idempotent. Also restrict this path to Safaricom's IP ranges at your proxy/firewall
    (see docs/DEPLOYMENT.md). We always answer 200 so Safaricom doesn't retry, and never reveal why we ignored one.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def post(self, request, secret):
        expected = settings.MPESA_CONFIG["CALLBACK_SECRET"]
        if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            result = get_payment_adapter(settings).parse_callback(request.data)
        except (PaymentError, NotImplementedError) as exc:
            logger.warning("Ignored malformed/unsupported M-Pesa callback: %s", exc)
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        payment = Payment.objects.filter(provider="mpesa", provider_reference=result.checkout_request_id,
                                         status="pending").first()
        if payment is None:
            logger.warning("M-Pesa callback for unknown/settled CheckoutRequestID %s", result.checkout_request_id)
        else:
            apply_payment_result(payment.id, success=result.success, receipt=result.receipt_number,
                                 paid_amount=result.amount, description=result.result_description)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
