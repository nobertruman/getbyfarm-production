import logging
from decimal import ROUND_CEILING, Decimal

from django.db import transaction

from invoices.models import generate_invoice_for_order
from notifications.models import notify
from orders.models import Order
from suppliers.models import SupplierUser
from .models import Payment

logger = logging.getLogger(__name__)


def amount_to_charge(order: Order) -> Decimal:
    """M-Pesa moves whole shillings. Round UP so the supplier is never short by a fraction."""
    return order.total_amount.quantize(Decimal("1"), rounding=ROUND_CEILING)


@transaction.atomic
def apply_payment_result(payment_id, *, success: bool, receipt: str = "", paid_amount=None, description: str = "") -> Payment:
    """Idempotent: Safaricom may deliver the same callback more than once."""
    payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_id)
    if payment.status != "pending":
        return payment  # already settled; ignore duplicate delivery

    if not success:
        payment.status = "failed"
        payment.result_description = description[:255]
        payment.save(update_fields=["status", "result_description", "updated_at"])
        return payment

    if paid_amount is not None and Decimal(paid_amount) != payment.amount:
        # Money moved but not the amount we asked for. Do not guess: leave it pending and shout.
        logger.error("PAYMENT AMOUNT MISMATCH payment=%s expected=%s got=%s receipt=%s — reconcile manually",
                     payment.id, payment.amount, paid_amount, receipt)
        payment.result_description = f"Amount mismatch (got {paid_amount}); needs manual reconciliation."[:255]
        payment.save(update_fields=["result_description", "updated_at"])
        return payment

    payment.status = "success"
    payment.provider_reference = receipt or payment.provider_reference
    payment.result_description = description[:255]
    payment.save(update_fields=["status", "provider_reference", "result_description", "updated_at"])

    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == "submitted":
        order.transition_to("confirmed")
    else:
        # e.g. the order was cancelled while the STK prompt was open. The buyer HAS paid: flag for refund.
        logger.error("Payment %s succeeded but order %s is '%s' — refund/reconcile manually",
                     payment.id, order.order_number, order.status)

    generate_invoice_for_order(order)

    notify(order.placed_by, "Payment received", f"Order {order.order_number} is paid and confirmed.")
    for su in SupplierUser.objects.filter(supplier__order_allocations__order=order).select_related("user").distinct():
        notify(su.user, "New paid order", f"Order {order.order_number} is ready for you to accept.")
    return payment
