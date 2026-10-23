from django.db import migrations

# Reference data, not demo data: the platform needs at least one active country to accept signups.
# Add further countries (and flip is_active) from the Django admin as you expand.
COUNTRIES = [
    ("KE", "Kenya", "KES", "16.00", True),
    ("UG", "Uganda", "UGX", "18.00", False),
    ("TZ", "Tanzania", "TZS", "18.00", False),
    ("RW", "Rwanda", "RWF", "18.00", False),
]


def seed(apps, schema_editor):
    Country = apps.get_model("organizations", "Country")
    for code, name, currency, tax, active in COUNTRIES:
        Country.objects.get_or_create(
            code=code,
            defaults={"name": name, "currency_code": currency, "default_tax_rate": tax, "is_active": active},
        )


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
