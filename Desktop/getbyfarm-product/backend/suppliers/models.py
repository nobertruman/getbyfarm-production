import uuid
from django.db import models
from organizations.models import Country


VERIFICATION_STATUSES = [
    ("pending", "Pending"),
    ("under_review", "Under Review"),
    ("verified", "Verified"),
    ("suspended", "Suspended"),
    ("rejected", "Rejected"),
]


class SupplierOrganization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_name = models.CharField(max_length=200)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="suppliers")
    kra_pin = models.CharField(max_length=20, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    operating_location = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUSES, default="pending")
    reliability_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    quality_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    on_time_delivery_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Payout details are sensitive — never serialized to buyer-facing endpoints.
    payout_details = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.business_name

    def transition_status(self, new_status: str):
        """Enforce a valid verification-status transition graph rather than free-form writes."""
        valid_transitions = {
            "pending": {"under_review", "rejected"},
            "under_review": {"verified", "rejected"},
            "verified": {"suspended"},
            "suspended": {"verified", "rejected"},
            "rejected": {"pending"},
        }
        if new_status not in valid_transitions.get(self.verification_status, set()):
            raise ValueError(
                f"Cannot transition supplier from '{self.verification_status}' to '{new_status}'"
            )
        self.verification_status = new_status
        self.save(update_fields=["verification_status", "updated_at"])


class SupplierDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50)   # 'kra_cert', 'business_permit', ...
    file_url = models.URLField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)


class SupplierUser(models.Model):
    """Links an accounts.User to the supplier org they work for (1:1 per user)."""
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True)
    supplier = models.ForeignKey(SupplierOrganization, on_delete=models.CASCADE, related_name="staff")
