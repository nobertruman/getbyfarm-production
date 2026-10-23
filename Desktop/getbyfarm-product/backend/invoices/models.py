import uuid
from django.db import models
from django.utils import timezone
from orders.models import Order


class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = [("unpaid", "Unpaid"), ("paid", "Paid"), ("partial", "Partial")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=30, unique=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid")

    # Placeholder only — no eTIMS integration exists yet. Left nullable and unused
    # rather than fabricating a fake reference, per spec section 20 ("do not hard-code
    # assumptions where official API requirements may change").
    etims_reference = models.CharField(max_length=100, blank=True, null=True)

    issued_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_invoice_number() -> str:
        return f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    def __str__(self):
        return self.invoice_number


def generate_invoice_for_order(order: Order) -> Invoice:
    """Idempotent — calling this twice for the same order returns the existing invoice."""
    existing = order.invoices.first()
    if existing:
        return existing
    return Invoice.objects.create(
        order=order,
        invoice_number=Invoice.generate_invoice_number(),
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        delivery_fee=order.delivery_fee,
        total_amount=order.total_amount,
        payment_status="paid" if order.payments.filter(status="success").exists() else "unpaid",
    )
