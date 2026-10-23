"""
Creates FICTIONAL demo businesses, users and prices so a staging/demo site has something to show.

    python manage.py seed_demo_data --i-know-this-is-demo [--password '...']

Refuses to run unless you pass the flag, so fake suppliers can't land in a real production database by
accident. Demo accounts use the reserved .test TLD. All prices are made-up sample values.
"""
import secrets
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from catalog.models import Product
from organizations.models import Branch, Country, Organization
from pricing.models import SupplierPrice
from suppliers.models import SupplierOrganization, SupplierUser

DOMAIN = "demo.getbyfarm.test"

SUPPLIERS = [
    # name, location, reliability, quality, delivery, lead days
    ("Kilimo Fresh Wholesalers", "Marikiti, Nairobi", 94, 4.6, 300, 1),
    ("Wakulima Direct Supplies", "Wakulima Market, Nairobi", 78, 3.9, 550, 2),
    ("Green Basket Traders", "Kiambu Road, Nairobi", 88, 4.2, 400, 1),
    ("Mwea Grain Merchants", "Industrial Area, Nairobi", 91, 4.4, 500, 2),
    ("Sunrise Layers Farm", "Thika Road, Nairobi", 93, 4.5, 200, 1),
]

# product name -> {supplier index: unit price}. Sample numbers only.
PRICES = {
    "Tomatoes": {0: 92, 1: 85, 2: 89},
    "Onions (Red)": {0: 78, 1: 74, 2: 80},
    "Potatoes": {0: 55, 2: 58},
    "Pishori Rice (50kg)": {3: 6800},
    "Maize Flour (2kg)": {3: 190},
    "Sugar (1kg)": {3: 210},
    "Eggs (Tray of 30)": {4: 420},
}


class Command(BaseCommand):
    help = "Create fictional demo data (staging/demo only)."

    def add_arguments(self, parser):
        parser.add_argument("--i-know-this-is-demo", action="store_true", dest="confirm")
        parser.add_argument("--password", default="")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not opts["confirm"]:
            raise CommandError("Refusing to create fake accounts without --i-know-this-is-demo.")
        if not Product.objects.exists():
            raise CommandError("Run `manage.py seed_catalogue` first.")
        password = opts["password"] or secrets.token_urlsafe(12)
        country = Country.objects.get(code="KE")

        org, _ = Organization.objects.get_or_create(name="Savannah Bites Ltd (demo)", defaults={"country": country})
        branch, _ = Branch.objects.get_or_create(organization=org, name="Nairobi CBD",
                                                 defaults={"address": "Kenyatta Avenue, Nairobi"})
        buyer, created = User.objects.get_or_create(email=f"chef@{DOMAIN}", defaults={
            "full_name": "Amina Chef (demo)", "organization": org, "branch": branch})
        if created:
            buyer.set_password(password)
            buyer.save()
            buyer.roles.add(Role.objects.get(code="enterprise_admin"))

        suppliers = []
        for i, (name, loc, rel, qual, _, _) in enumerate(SUPPLIERS):
            s, new = SupplierOrganization.objects.get_or_create(
                business_name=f"{name} (demo)", defaults={
                    "country": country, "operating_location": loc, "verification_status": "verified",
                    "reliability_score": rel, "quality_rating": qual})
            suppliers.append(s)
            user, ucreated = User.objects.get_or_create(email=f"supplier{i + 1}@{DOMAIN}", defaults={
                "full_name": f"{name} staff (demo)"})
            if ucreated:
                user.set_password(password)
                user.save()
                user.roles.add(Role.objects.get(code="supplier_admin"))
                SupplierUser.objects.create(user=user, supplier=s)

        for product_name, offers in PRICES.items():
            product = Product.objects.filter(name=product_name).first()
            if not product:
                continue
            for idx, price in offers.items():
                delivery, lead = SUPPLIERS[idx][4], SUPPLIERS[idx][5]
                SupplierPrice.objects.get_or_create(supplier=suppliers[idx], product=product, defaults={
                    "unit_price": Decimal(price), "stock_quantity": Decimal("500"),
                    "minimum_order_quantity": Decimal("1"), "delivery_cost_flat": Decimal(delivery),
                    "lead_time_days": Decimal(lead)})

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"  Buyer:    chef@{DOMAIN}")
        self.stdout.write(f"  Supplier: supplier1@{DOMAIN} … supplier5@{DOMAIN}")
        if not opts["password"]:
            self.stdout.write(f"  Password (shown once): {password}")
