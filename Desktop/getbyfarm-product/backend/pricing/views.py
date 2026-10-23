from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Min
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import PriceHistory, SupplierPrice


def _supplier_user(user):
    return getattr(user, "supplieruser", None)


class SupplierPriceSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit = serializers.CharField(source="product.default_unit", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)

    class Meta:
        model = SupplierPrice
        fields = ["id", "supplier", "product", "product_name", "unit", "category_name", "unit_price",
                  "currency_code", "stock_quantity", "minimum_order_quantity", "delivery_areas",
                  "delivery_cost_flat", "lead_time_days", "is_active", "updated_at"]
        read_only_fields = ["id", "updated_at", "currency_code"]
        extra_kwargs = {"supplier": {"required": False}}

    def validate_unit_price(self, v):
        if v <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return v

    def validate_stock_quantity(self, v):
        if v < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return v

    def validate_minimum_order_quantity(self, v):
        if v <= 0:
            raise serializers.ValidationError("Minimum order quantity must be greater than zero.")
        return v

    def validate_delivery_cost_flat(self, v):
        if v < 0:
            raise serializers.ValidationError("Delivery cost cannot be negative.")
        return v

    def validate(self, attrs):
        # A product can only be priced once per supplier (variants are Phase 2).
        request = self.context["request"]
        su = _supplier_user(request.user)
        supplier_id = su.supplier_id if su and not request.user.is_staff else attrs.get("supplier") and attrs["supplier"].id
        product = attrs.get("product")
        if self.instance is None and product and supplier_id:
            if SupplierPrice.objects.filter(supplier_id=supplier_id, product=product, is_active=True).exists():
                raise serializers.ValidationError({"product": "You already list this product. Edit the existing listing."})
        return attrs


class SupplierWritePermission(permissions.BasePermission):
    """Anyone signed-in may read listings; only the owning supplier's staff (or platform admin) may write."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or _supplier_user(request.user)))

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS or request.user.is_staff:
            return True
        su = _supplier_user(request.user)
        return bool(su and su.supplier_id == obj.supplier_id)


class SupplierPriceViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierPriceSerializer
    permission_classes = [SupplierWritePermission]
    filterset_fields = ["product", "supplier"]

    def get_queryset(self):
        user = self.request.user
        qs = SupplierPrice.objects.select_related("product__category", "supplier").order_by("product__name")
        if user.is_staff:
            return qs
        su = _supplier_user(user)
        if su:
            return qs.filter(supplier_id=su.supplier_id, is_active=True)
        # Buyers: only live offers from verified suppliers.
        return qs.filter(is_active=True, supplier__verification_status="verified", supplier__deleted_at__isnull=True)

    def perform_create(self, serializer):
        su = _supplier_user(self.request.user)
        if su and not self.request.user.is_staff:
            serializer.save(supplier_id=su.supplier_id)
        elif "supplier" not in serializer.validated_data:
            raise serializers.ValidationError({"supplier": "Required for platform admins."})
        else:
            serializer.save()

    def perform_update(self, serializer):
        # A supplier can never re-assign a listing to another supplier.
        if not self.request.user.is_staff:
            serializer.validated_data.pop("supplier", None)
        serializer.save()

    def perform_destroy(self, instance):  # soft delete: keep history, stop selling
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @action(detail=False, methods=["get"], url_path=r"price-intelligence/(?P<product_id>[^/.]+)")
    def price_intelligence(self, request, product_id=None):
        """Best current price vs 30- and 90-day averages for a product."""
        now = timezone.now()
        live = SupplierPrice.objects.filter(product_id=product_id, is_active=True, supplier__verification_status="verified")
        best = live.aggregate(m=Min("unit_price"))["m"]
        hist = PriceHistory.objects.filter(product_id=product_id)
        avg30 = hist.filter(recorded_at__gte=now - timedelta(days=30)).aggregate(a=Avg("unit_price"))["a"]
        avg90 = hist.filter(recorded_at__gte=now - timedelta(days=90)).aggregate(a=Avg("unit_price"))["a"]

        note = None
        if best is not None and avg30:
            if best > Decimal(avg30) * Decimal("1.10"):
                note = "The best current price is above the 30-day average. Consider waiting or alternative products."
            elif best < Decimal(avg30) * Decimal("0.90"):
                note = "The best current price is below the 30-day average — a good time to stock up."
        return Response({"product_id": product_id, "best_current_price": best, "avg_30_day": avg30,
                         "avg_90_day": avg90, "note": note})
