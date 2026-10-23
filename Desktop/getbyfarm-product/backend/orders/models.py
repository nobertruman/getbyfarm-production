import uuid
from django.db import models
from django.utils import timezone
from organizations.models import Branch
from catalog.models import Product
from suppliers.models import SupplierOrganization
from accounts.models import User


ORDER_STATUSES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("confirmed", "Confirmed"),
    ("processing", "Processing"),
    ("ready_for_dispatch", "Ready for Dispatch"),
    ("in_transit", "In Transit"),
    ("delivered", "Delivered"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

# Valid forward transitions. Cancellation is allowed from any pre-delivery state.
ORDER_TRANSITIONS = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"confirmed", "cancelled"},
    "confirmed": {"processing", "cancelled"},
    "processing": {"ready_for_dispatch", "cancelled"},
    "ready_for_dispatch": {"in_transit", "cancelled"},
    "in_transit": {"delivered"},
    "delivered": {"completed"},
    "completed": set(),
    "cancelled": set(),
}

ALLOCATION_STATUSES = [
    ("new", "New"),
    ("accepted", "Accepted"),
    ("preparing", "Preparing"),
    ("ready", "Ready"),
    ("dispatched", "Dispatched"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
]


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUSES, default="draft")

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    placed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders_placed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def transition_to(self, new_status: str):
        allowed = ORDER_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Cannot move order from '{self.status}' to '{new_status}'")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])

    @staticmethod
    def generate_order_number() -> str:
        return f"GBF-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)


class OrderAllocation(models.Model):
    """An order is split into one allocation per supplier — each supplier only
    sees and manages their own slice of the order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="allocations")
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.PROTECT, related_name="order_allocations")
    status = models.CharField(max_length=20, choices=ALLOCATION_STATUSES, default="new")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def transition_to(self, new_status: str):
        allowed = {
            "new": {"accepted", "cancelled"},
            "accepted": {"preparing", "cancelled"},
            "preparing": {"ready", "cancelled"},
            "ready": {"dispatched"},
            "dispatched": {"delivered"},
            "delivered": set(),
            "cancelled": set(),
        }.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Cannot move allocation from '{self.status}' to '{new_status}'")
        self.status = new_status
        self.save(update_fields=["status"])


class PurchaseApproval(models.Model):
    """Enterprise approval chain — thresholds are configured per organization (Phase 2 config UI),
    but the model supports it from MVP so multi-branch chains don't require a schema change later."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="approvals")
    approver_role = models.CharField(max_length=30)   # 'manager' | 'procurement' | 'finance'
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, default="pending",
                               choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")])
    threshold_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
