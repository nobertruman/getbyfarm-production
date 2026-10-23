import uuid
from django.db import models
from orders.models import OrderAllocation


class DeliveryPartner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    is_internal = models.BooleanField(default=False)   # false = 3rd-party logistics provider

    def __str__(self):
        return self.name


class Delivery(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"), ("dispatched", "Dispatched"),
        ("in_transit", "In Transit"), ("delivered", "Delivered"), ("failed", "Failed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_allocation = models.OneToOneField(OrderAllocation, on_delete=models.CASCADE, related_name="delivery")
    delivery_partner = models.ForeignKey(DeliveryPartner, on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address = models.TextField()
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    proof_of_delivery_url = models.URLField(blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def record_status(self, new_status: str, note: str = ""):
        self.status = new_status
        if new_status == "delivered":
            from django.utils import timezone
            self.delivered_at = timezone.now()
        self.save()
        DeliveryTracking.objects.create(delivery=self, status=new_status, note=note)


class DeliveryTracking(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="tracking_events")
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
