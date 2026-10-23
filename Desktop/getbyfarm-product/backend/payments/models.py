import uuid
from django.db import models
from orders.models import Order


class Payment(models.Model):
    PROVIDER_CHOICES = [("mpesa", "M-Pesa"), ("card", "Card"), ("bank", "Bank Transfer")]
    STATUS_CHOICES = [
        ("pending", "Pending"), ("success", "Success"),
        ("failed", "Failed"), ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default="mpesa")
    provider_reference = models.CharField(max_length=100, blank=True, db_index=True)   # checkout id, later receipt no.
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    result_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order"], condition=models.Q(status__in=["pending", "success"]),
                name="one_live_payment_per_order",
            )
        ]

    def __str__(self):
        return f"{self.provider} payment {self.amount} for {self.order.order_number} [{self.status}]"
