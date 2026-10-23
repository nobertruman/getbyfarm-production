import uuid
from django.db import models


class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)          # ISO 3166-1 alpha-2
    name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3)               # ISO 4217
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


SUBSCRIPTION_TIERS = [
    ("starter", "Starter"),
    ("business", "Business"),
    ("professional", "Professional"),
    ("enterprise", "Enterprise"),
]


class Organization(models.Model):
    """A buyer business, e.g. a restaurant group with multiple branches."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="organizations")
    kra_pin = models.CharField(max_length=20, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_TIERS, default="starter")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    monthly_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.organization.name} — {self.name}"
