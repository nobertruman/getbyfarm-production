"""
Loads the starting product catalogue (categories + common hospitality SKUs). No prices, no suppliers, no users:
this is reference data and is safe to run in production. Idempotent: re-running adds only what's missing.

    python manage.py seed_catalogue
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import Category, Product

CATALOGUE = {
    "Fresh Produce": [
        ("Tomatoes", "kg"), ("Onions (Red)", "kg"), ("Potatoes", "kg"), ("Carrots", "kg"), ("Cabbage", "kg"),
        ("Kale (Sukuma Wiki)", "bunch"), ("Spinach", "bunch"), ("Capsicum (Green)", "kg"), ("Garlic", "kg"),
        ("Bananas", "kg"), ("Avocados", "kg"), ("Lemons", "kg"), ("Coriander", "bunch"),
    ],
    "Meat & Protein": [
        ("Whole Chicken", "kg"), ("Beef (Boneless)", "kg"), ("Goat Meat", "kg"), ("Tilapia (Whole)", "kg"),
        ("Eggs (Tray of 30)", "tray"), ("Sausages", "kg"),
    ],
    "Dry Foods": [
        ("Pishori Rice (50kg)", "bag"), ("Maize Flour (2kg)", "pack"), ("Wheat Flour (2kg)", "pack"),
        ("Sugar (1kg)", "kg"), ("Salt (1kg)", "kg"), ("Beans (Rosecoco)", "kg"), ("Spaghetti (500g)", "pack"),
        ("Tea Leaves (500g)", "pack"), ("Coffee (Ground, 500g)", "pack"),
    ],
    "Beverages": [
        ("Bottled Water (500ml, 24)", "carton"), ("Soda 300ml (24)", "crate"), ("Fruit Juice 1L", "carton"),
        ("Milk (Fresh, 500ml)", "packet"), ("Tonic Water 300ml (24)", "crate"),
    ],
    "Kitchen Supplies": [
        ("Cooking Oil (20L)", "jerrycan"), ("Cooking Oil (5L)", "bottle"), ("Aluminium Foil (45cm)", "roll"),
        ("Cling Film (45cm)", "roll"), ("Disposable Gloves (100)", "box"), ("Food Containers 750ml (50)", "pack"),
    ],
    "Cleaning": [
        ("Industrial Detergent (5L)", "jug"), ("Disinfectant (5L)", "jug"), ("Toilet Tissue (10 rolls)", "pack"),
        ("Paper Towels", "roll"), ("Dishwashing Liquid (5L)", "jug"), ("Bleach (5L)", "jug"),
    ],
    "Packaging": [
        ("Takeaway Boxes (Kraft, 100)", "pack"), ("Paper Cups 8oz (50)", "sleeve"),
        ("Carrier Bags (Medium, 100)", "pack"), ("Napkins (100)", "pack"), ("Cutlery Set (Wooden, 100)", "pack"),
    ],
}


class Command(BaseCommand):
    help = "Load the starting product catalogue (safe for production)."

    def handle(self, *args, **opts):
        created = 0
        for cat_name, items in CATALOGUE.items():
            category, _ = Category.objects.get_or_create(slug=slugify(cat_name), defaults={"name": cat_name})
            for name, unit in items:
                _, new = Product.objects.get_or_create(category=category, name=name, defaults={"default_unit": unit})
                created += int(new)
        self.stdout.write(self.style.SUCCESS(f"Catalogue ready ({created} new products, "
                                              f"{Product.objects.count()} total)."))
