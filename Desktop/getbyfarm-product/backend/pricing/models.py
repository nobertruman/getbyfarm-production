import uuid
from django.db import models
from django.utils import timezone
from catalog.models import Product, ProductVariant
from suppliers.models import SupplierOrganization


class SupplierPrice(models.Model):
    """A supplier's current live offer for a product (optionally a specific variant)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.CASCADE, related_name="prices")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="supplier_prices")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)

    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="KES")
    stock_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    minimum_order_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1)
    delivery_areas = models.JSONField(default=list, blank=True)   # list of area names/geofence ids
    delivery_cost_flat = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lead_time_days = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["supplier"]),
        ]

    def save(self, *args, **kwargs):
        """Every price change is snapshotted to PriceHistory for price-intelligence charts."""
        is_new = self._state.adding
        price_changed = True
        if not is_new:
            previous = SupplierPrice.objects.filter(pk=self.pk).values_list("unit_price", flat=True).first()
            price_changed = previous is None or previous != self.unit_price
        super().save(*args, **kwargs)
        if price_changed:
            PriceHistory.objects.create(
                product=self.product,
                supplier=self.supplier,
                unit_price=self.unit_price,
                recorded_at=timezone.now(),
            )

    def __str__(self):
        return f"{self.supplier.business_name} — {self.product.name} @ {self.unit_price}"


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="price_history")
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.CASCADE, related_name="price_history")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["product", "recorded_at"])]
        ordering = ["-recorded_at"]
