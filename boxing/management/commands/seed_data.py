"""
Management command: seed_data

Usage:
    python manage.py seed_data

Inserts a realistic set of sample Products and Boxes, then prints a summary.
Running the command a second time is safe — it uses get_or_create so it will
not duplicate rows.
"""

from django.core.management.base import BaseCommand

from boxing.models import Box, Product


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

PRODUCTS = [
    # name, length, width, height (cm), weight (kg)
    ("Smartphone",      15.0, 8.0,  1.5,  0.200),
    ("Laptop 15-inch",  38.0, 27.0, 3.0,  2.100),
    ("Coffee Mug",      12.0, 12.0, 12.0, 0.350),
    ("Running Shoes",   32.0, 18.0, 14.0, 0.900),
    ("Yoga Mat",        61.0, 15.0, 15.0, 1.500),
    ("Paperback Book",  21.0, 15.0, 2.5,  0.250),
    ("Bluetooth Speaker", 18.0, 10.0, 10.0, 0.600),
    ("Water Bottle",    28.0,  8.0,  8.0, 0.450),
]

BOXES = [
    # name, int_length, int_width, int_height (cm), max_weight (kg), cost ($)
    ("XS Padded Envelope", 22.0, 16.0,  3.0,  1.0,   0.80),
    ("S Box",              30.0, 22.0, 10.0,  5.0,   1.50),
    ("M Box",              40.0, 30.0, 20.0, 10.0,   2.50),
    ("L Box",              60.0, 40.0, 30.0, 20.0,   4.00),
    ("XL Box",             80.0, 60.0, 40.0, 30.0,   6.50),
    ("Shoe Box",           35.0, 20.0, 15.0,  5.0,   1.80),
]


class Command(BaseCommand):
    help = "Seed the database with sample Products and Boxes."

    def handle(self, *args, **options) -> None:
        self.stdout.write("Seeding products …")
        for name, l, w, h, wt in PRODUCTS:
            obj, created = Product.objects.get_or_create(
                name=name,
                defaults={"length": l, "width": w, "height": h, "weight": wt},
            )
            status = "created" if created else "already exists"
            self.stdout.write(f"  Product '{name}': {status}")

        self.stdout.write("Seeding boxes …")
        for name, il, iw, ih, mw, cost in BOXES:
            obj, created = Box.objects.get_or_create(
                name=name,
                defaults={
                    "internal_length": il,
                    "internal_width": iw,
                    "internal_height": ih,
                    "max_weight": mw,
                    "cost": cost,
                },
            )
            status = "created" if created else "already exists"
            self.stdout.write(f"  Box '{name}': {status}")

        self.stdout.write(self.style.SUCCESS("Done!"))
