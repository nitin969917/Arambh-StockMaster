from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from inventory.models import (
    Location,
    Product,
    ProductCategory,
    ReorderRule,
    StockDocument,
    StockMoveLine,
    StockQuant,
    Warehouse,
)


class Command(BaseCommand):
    help = "Seed demo data for StockMaster IMS (users, warehouses, products, and stock flows)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # Users
        manager, _ = User.objects.get_or_create(
            username="manager01",
            defaults={
                "email": "manager@example.com",
                "role": User.Roles.INVENTORY_MANAGER,
            },
        )
        if not manager.password:
            manager.set_password("Manager@123")
            manager.save()

        staff, _ = User.objects.get_or_create(
            username="worker01",
            defaults={
                "email": "worker@example.com",
                "role": User.Roles.WAREHOUSE_STAFF,
            },
        )
        if not staff.password:
            staff.set_password("Worker@123")
            staff.save()

        # Warehouses & locations
        main_wh, _ = Warehouse.objects.get_or_create(code="WH", defaults={"name": "Main Warehouse"})
        prod_wh, _ = Warehouse.objects.get_or_create(code="PROD", defaults={"name": "Production Floor"})

        wh_stock1, _ = Location.objects.get_or_create(
            warehouse=main_wh, code="STOCK1", defaults={"name": "Main Stock 1", "is_default": True}
        )
        wh_stock2, _ = Location.objects.get_or_create(
            warehouse=main_wh, code="STOCK2", defaults={"name": "Main Stock 2"}
        )
        prod_rack, _ = Location.objects.get_or_create(
            warehouse=prod_wh, code="RACK1", defaults={"name": "Production Rack"}
        )

        # Categories & products
        furn_cat, _ = ProductCategory.objects.get_or_create(name="Furniture")
        raw_cat, _ = ProductCategory.objects.get_or_create(name="Raw Material")
        consum_cat, _ = ProductCategory.objects.get_or_create(name="Consumable")

        desk, _ = Product.objects.get_or_create(
            sku="DESK001",
            defaults={
                "name": "Office Desk",
                "category": furn_cat,
                "unit_of_measure": "Unit",
                "initial_stock": 0,
            },
        )
        chair, _ = Product.objects.get_or_create(
            sku="CHAIR001",
            defaults={
                "name": "Office Chair",
                "category": furn_cat,
                "unit_of_measure": "Unit",
                "initial_stock": 0,
            },
        )
        steel, _ = Product.objects.get_or_create(
            sku="STEEL100",
            defaults={
                "name": "Steel Rod",
                "category": raw_cat,
                "unit_of_measure": "Kg",
                "initial_stock": 0,
            },
        )
        screw, _ = Product.objects.get_or_create(
            sku="SCRW01",
            defaults={
                "name": "Screw Pack",
                "category": consum_cat,
                "unit_of_measure": "Pack",
                "initial_stock": 0,
            },
        )

        # Initial stock (quants)
        StockQuant.objects.update_or_create(
            product=steel,
            location=wh_stock1,
            defaults={"quantity": 100},
        )
        StockQuant.objects.update_or_create(
            product=desk,
            location=wh_stock1,
            defaults={"quantity": 20},
        )
        StockQuant.objects.update_or_create(
            product=chair,
            location=wh_stock1,
            defaults={"quantity": 15},
        )
        StockQuant.objects.update_or_create(
            product=screw,
            location=wh_stock1,
            defaults={"quantity": 200},
        )

        # Reorder rules
        ReorderRule.objects.get_or_create(
            product=steel,
            warehouse=main_wh,
            defaults={"min_quantity": 20, "max_quantity": 150},
        )
        ReorderRule.objects.get_or_create(
            product=desk,
            warehouse=main_wh,
            defaults={"min_quantity": 5, "max_quantity": 40},
        )
        ReorderRule.objects.get_or_create(
            product=chair,
            warehouse=main_wh,
            defaults={"min_quantity": 3, "max_quantity": 25},
        )
        ReorderRule.objects.get_or_create(
            product=screw,
            warehouse=main_wh,
            defaults={"min_quantity": 50, "max_quantity": 300},
        )

        today = date.today()

        # Incoming receipts (examples of vendor deliveries)
        receipt, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.RECEIPT,
            reference="WH/IN/0001",
            defaults={
                "destination_location": wh_stock1,
                "scheduled_date": today - timedelta(days=1),
                "status": StockDocument.Status.DONE,
                "contact_name": "Azure Interior",
                "created_by": manager,
            },
        )
        if not receipt.lines.exists():
            StockMoveLine.objects.create(document=receipt, product=steel, quantity=50)
            StockMoveLine.objects.create(document=receipt, product=screw, quantity=100)

        receipt2, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.RECEIPT,
            reference="WH/IN/0002",
            defaults={
                "destination_location": wh_stock1,
                "scheduled_date": today,
                "status": StockDocument.Status.DONE,
                "contact_name": "Deco Addict",
                "created_by": manager,
            },
        )
        if not receipt2.lines.exists():
            StockMoveLine.objects.create(document=receipt2, product=desk, quantity=10)
            StockMoveLine.objects.create(document=receipt2, product=chair, quantity=5)

        # Third receipt so dashboard shows 3 total receipt operations
        receipt3, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.RECEIPT,
            reference="WH/IN/0003",
            defaults={
                "destination_location": wh_stock2,
                "scheduled_date": today - timedelta(days=3),
                "status": StockDocument.Status.DONE,
                "contact_name": "Vendor Y",
                "created_by": manager,
            },
        )
        if not receipt3.lines.exists():
            StockMoveLine.objects.create(document=receipt3, product=screw, quantity=50)

        # Internal transfer example
        transfer, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.INTERNAL,
            reference="INT/0001",
            defaults={
                "source_location": wh_stock1,
                "destination_location": prod_rack,
                "scheduled_date": today - timedelta(days=2),
                "status": StockDocument.Status.DONE,
                "contact_name": "Internal Move",
                "created_by": staff,
            },
        )
        if not transfer.lines.exists():
            StockMoveLine.objects.create(document=transfer, product=steel, quantity=20)

        # Outgoing deliveries
        del1, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.DELIVERY,
            reference="WH/OUT/0001",
            defaults={
                "source_location": wh_stock1,
                "destination_location": prod_rack,
                "scheduled_date": today,
                "status": StockDocument.Status.DONE,
                "contact_name": "Azure Interior",
                "created_by": manager,
            },
        )
        if not del1.lines.exists():
            StockMoveLine.objects.create(document=del1, product=desk, quantity=6)

        del2, _ = StockDocument.objects.get_or_create(
            doc_type=StockDocument.DocTypes.DELIVERY,
            reference="WH/OUT/0002",
            defaults={
                "source_location": wh_stock1,
                "destination_location": wh_stock2,
                "scheduled_date": today + timedelta(days=1),
                "status": StockDocument.Status.DONE,
                "contact_name": "Vendor X",
                "created_by": manager,
            },
        )
        if not del2.lines.exists():
            StockMoveLine.objects.create(document=del2, product=desk, quantity=30)  # Intentionally high for shortage

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write("Login with manager01 / Manager@123 or worker01 / Worker@123.")


