from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Warehouse(TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Location(TimeStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("warehouse", "code")

    def __str__(self) -> str:
        return f"{self.warehouse.code}:{self.code}"


class ProductCategory(TimeStampedModel):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    unit_of_measure = models.CharField(max_length=50, default="Unit")
    initial_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_stock_alert = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Alert threshold: Show low stock warning when stock goes below this value"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class ReorderRule(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reorder_rules")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="reorder_rules")
    min_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    max_quantity = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"Reorder {self.product} @ {self.warehouse}"


class StockDocument(TimeStampedModel):
    class DocTypes(models.TextChoices):
        RECEIPT = "receipt", "Receipt (Incoming)"
        DELIVERY = "delivery", "Delivery Order (Outgoing)"
        INTERNAL = "internal", "Internal Transfer"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        WAITING = "waiting", "Waiting"
        READY = "ready", "Ready"
        DONE = "done", "Done"
        CANCELED = "canceled", "Canceled"

    doc_type = models.CharField(max_length=20, choices=DocTypes.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reference = models.CharField(max_length=100, blank=True)
    contact_name = models.CharField(max_length=255, blank=True, help_text="Vendor/Supplier name for Receipts, Customer name for Deliveries")
    delivery_address = models.TextField(blank=True, help_text="Delivery address for customer (Deliveries) or vendor address (Receipts)")

    source_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_documents",
    )
    destination_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destination_documents",
    )

    scheduled_date = models.DateField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_documents"
    )

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} #{self.id or 'new'}"


class StockMoveLine(TimeStampedModel):
    document = models.ForeignKey(StockDocument, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_moves")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity} on {self.document}"


class StockQuant(TimeStampedModel):
    """
    On-hand quantity per product and location.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="quants")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="quants")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = ("product", "location")

    def __str__(self) -> str:
        return f"{self.product} @ {self.location}: {self.quantity}"


class StockLedgerEntry(TimeStampedModel):
    """
    Immutable log of stock movements used for move history.
    """

    document = models.ForeignKey(
        StockDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="ledger_entries")
    source_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_source_entries",
    )
    destination_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_destination_entries",
    )
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"[{self.created_at.date()}] {self.product} Δ{self.quantity_delta}"
