import uuid
from django.db import models
from organizations.models import Branch
from pricing.models import SupplierPrice


class Cart(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("checked_out", "Checked Out"),
        ("abandoned", "Abandoned"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="carts")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch"], condition=models.Q(status="open"), name="one_open_cart_per_branch"
            )
        ]

    def recompute_totals(self):
        """Delivery fees are charged once per distinct supplier in the cart, not per line item."""
        items = list(self.items.select_related("supplier_price"))
        subtotal = sum((i.locked_unit_price * i.quantity for i in items), start=0)
        delivery_by_supplier = {
            i.supplier_price.supplier_id: i.supplier_price.delivery_cost_flat for i in items
        }
        delivery_total = sum(delivery_by_supplier.values(), start=0)
        return {"subtotal": subtotal, "delivery_total": delivery_total, "total": subtotal + delivery_total}

    def __str__(self):
        return f"Cart {self.id} ({self.branch.name})"


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    supplier_price = models.ForeignKey(SupplierPrice, on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    # Snapshot price + engine explanation at the moment the buyer added this line,
    # so later price changes at the supplier don't silently change what the buyer agreed to.
    locked_unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    recommendation_reason = models.TextField(blank=True)

    @property
    def line_total(self):
        return self.locked_unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.supplier_price.product.name}"
