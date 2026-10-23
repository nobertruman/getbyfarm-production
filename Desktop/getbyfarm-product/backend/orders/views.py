from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Order, OrderAllocation, OrderItem, PurchaseApproval


def _error(exc: Exception, code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": str(exc)}, status=code)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit = serializers.CharField(source="product.default_unit", read_only=True)
    supplier_name = serializers.CharField(source="supplier.business_name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "unit", "supplier", "supplier_name",
                  "quantity", "unit_price", "line_total"]


class OrderAllocationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.business_name", read_only=True)

    class Meta:
        model = OrderAllocation
        fields = ["id", "supplier", "supplier_name", "status", "subtotal"]


class PurchaseApprovalSerializer(serializers.ModelSerializer):
    can_decide = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseApproval
        fields = ["id", "approver_role", "status", "threshold_amount", "decided_at", "can_decide"]

    def get_can_decide(self, obj):
        request = self.context.get("request")
        return bool(request and obj.status == "pending" and services.user_can_approve(request.user, obj.approver_role))


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    allocations = OrderAllocationSerializer(many=True, read_only=True)
    approvals = PurchaseApprovalSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "order_number", "branch", "branch_name", "status", "subtotal", "delivery_fee",
                  "tax_amount", "total_amount", "items", "allocations", "approvals", "created_at"]
        read_only_fields = fields


class BuyerOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    The BUYER's view of orders. Suppliers never use this endpoint (they'd see other suppliers' prices);
    they work from /allocations/, which only exposes their own slice. Orders are created via cart checkout.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        qs = (Order.objects.select_related("branch")
              .prefetch_related("items__product", "items__supplier", "allocations__supplier", "approvals")
              .order_by("-created_at"))
        if user.is_staff:
            return qs
        if not user.branch_id:
            return qs.none()
        return qs.filter(branch_id=user.branch_id)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        order = self.get_object()
        try:
            services.submit(order)
        except services.OrderError as exc:
            return _error(exc)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            order = services.cancel_order(order)
        except services.OrderError as exc:
            return _error(exc)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        order = self.get_object()
        try:
            approval = order.approvals.get(pk=request.data.get("approval_id"), status="pending")
        except (PurchaseApproval.DoesNotExist, ValueError, DjangoValidationError):
            return _error("No matching pending approval.", status.HTTP_404_NOT_FOUND)
        try:
            services.approve(order, approval, request.user)
        except services.OrderError as exc:
            return _error(exc, status.HTTP_403_FORBIDDEN)
        order.refresh_from_db()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="confirm-receipt")
    def confirm_receipt(self, request, pk=None):
        order = self.get_object()
        try:
            services.confirm_receipt(order)
        except services.OrderError as exc:
            return _error(exc)
        return Response(self.get_serializer(order).data)


class SupplierAllocationSerializer(serializers.ModelSerializer):
    """What a supplier may see of an order: only its own items, plus where to deliver."""
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    placed_at = serializers.DateTimeField(source="order.created_at", read_only=True)
    buyer = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()

    class Meta:
        model = OrderAllocation
        fields = ["id", "order_number", "order_status", "placed_at", "status", "subtotal",
                  "buyer", "delivery_address", "items"]

    def get_buyer(self, obj):
        b = obj.order.branch
        return f"{b.organization.name} — {b.name}"

    def get_delivery_address(self, obj):
        return obj.order.branch.address

    def get_items(self, obj):
        return [
            {"product_name": i.product.name, "unit": i.product.default_unit,
             "quantity": str(i.quantity), "unit_price": str(i.unit_price), "line_total": str(i.line_total)}
            for i in obj.order.items.all() if i.supplier_id == obj.supplier_id
        ]


class SupplierAllocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The SUPPLIER's work queue. Only fulfilment-ready (paid) orders appear; each supplier sees only its own."""
    serializer_class = SupplierAllocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["status"]

    def get_queryset(self):
        user = self.request.user
        qs = (OrderAllocation.objects
              .select_related("order__branch__organization", "supplier")
              .prefetch_related("order__items__product")
              .exclude(order__status__in=["draft", "submitted", "cancelled"])
              .order_by("-order__created_at"))
        if user.is_staff:
            return qs
        su = getattr(user, "supplieruser", None)
        return qs.filter(supplier_id=su.supplier_id) if su else qs.none()

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        allocation = self.get_object()
        try:
            services.advance_allocation(allocation, request.data.get("status"))
        except services.OrderError as exc:
            return _error(exc)
        return Response(self.get_serializer(allocation).data)
