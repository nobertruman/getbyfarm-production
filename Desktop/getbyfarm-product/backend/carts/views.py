from decimal import Decimal

from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from orders.serializers_compat import serialize_order
from orders.services import OrderError, create_order_from_cart
from pricing.models import SupplierPrice
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="supplier_price.product.name", read_only=True)
    unit = serializers.CharField(source="supplier_price.product.default_unit", read_only=True)
    supplier_name = serializers.CharField(source="supplier_price.supplier.business_name", read_only=True)
    delivery_cost = serializers.DecimalField(source="supplier_price.delivery_cost_flat", max_digits=14,
                                             decimal_places=2, read_only=True)
    supplier_id = serializers.UUIDField(source="supplier_price.supplier_id", read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "supplier_price", "supplier_id", "product_name", "unit", "supplier_name", "quantity",
                  "locked_unit_price", "delivery_cost", "recommendation_reason", "line_total"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "branch", "status", "items", "totals", "created_at"]
        read_only_fields = fields

    def get_totals(self, obj):
        return {k: str(v) for k, v in obj.recompute_totals().items()}


class AddCartItemSerializer(serializers.Serializer):
    supplier_price_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    recommendation_reason = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)


class HasBranch(permissions.BasePermission):
    message = "Only buyer accounts with a branch can use a cart."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.branch_id)


class CartViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """A branch's open cart. Carts are created implicitly by add-item; they are never POSTed directly."""
    serializer_class = CartSerializer
    permission_classes = [HasBranch]

    def get_queryset(self):
        return (Cart.objects.filter(branch_id=self.request.user.branch_id, status="open")
                .prefetch_related("items__supplier_price__product", "items__supplier_price__supplier"))

    @action(detail=False, methods=["post"], url_path="add-item")
    def add_item(self, request):
        ser = AddCartItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        sp = (SupplierPrice.objects.select_related("supplier", "product")
              .filter(pk=data["supplier_price_id"], is_active=True, supplier__verification_status="verified",
                      supplier__deleted_at__isnull=True).first())
        if sp is None:
            return Response({"detail": "This offer is no longer available."}, status=status.HTTP_404_NOT_FOUND)
        if sp.stock_quantity < data["quantity"]:
            return Response({"detail": f"Only {sp.stock_quantity:g} in stock."}, status=status.HTTP_400_BAD_REQUEST)
        if data["quantity"] < sp.minimum_order_quantity:
            return Response({"detail": f"Minimum order is {sp.minimum_order_quantity:g}."},
                            status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Cart.objects.get_or_create(branch_id=request.user.branch_id, status="open")
        CartItem.objects.update_or_create(
            cart=cart, supplier_price=sp,
            defaults={"quantity": data["quantity"], "locked_unit_price": sp.unit_price,
                      "recommendation_reason": data["recommendation_reason"]},
        )
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="remove-item")
    def remove_item(self, request, pk=None):
        cart = self.get_object()
        deleted, _ = CartItem.objects.filter(cart=cart, id=request.data.get("item_id")).delete()
        if not deleted:
            return Response({"detail": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CartSerializer(cart).data)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        cart = self.get_object()
        try:
            order = create_order_from_cart(cart, placed_by=request.user)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        cart.status = "checked_out"
        cart.save(update_fields=["status", "updated_at"])
        return Response(serialize_order(order, request), status=status.HTTP_201_CREATED)
