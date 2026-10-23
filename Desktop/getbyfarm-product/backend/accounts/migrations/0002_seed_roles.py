from django.db import migrations

ROLES = [
    ("buyer_user", "Buyer user"),
    ("buyer_manager", "Buyer manager"),
    ("procurement_manager", "Procurement manager"),
    ("finance_manager", "Finance manager"),
    ("enterprise_admin", "Enterprise admin"),
    ("supplier_staff", "Supplier staff"),
    ("supplier_admin", "Supplier admin"),
    ("delivery_partner", "Delivery partner"),
    ("platform_admin", "Platform admin"),
]


def seed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name in ROLES:
        Role.objects.get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
