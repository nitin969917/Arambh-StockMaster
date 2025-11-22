from django.contrib import admin
from .models import (
    Warehouse,
    Location,
    ProductCategory,
    Product,
    ReorderRule,
    StockDocument,
    StockMoveLine,
    StockQuant,
    StockLedgerEntry,
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    """Admin for Warehouse model."""
    list_display = ['code', 'name', 'address', 'created_at']
    list_filter = ['created_at']
    search_fields = ['code', 'name', 'address']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location model."""
    list_display = ['code', 'name', 'warehouse', 'is_default', 'created_at']
    list_filter = ['warehouse', 'is_default', 'created_at']
    search_fields = ['code', 'name', 'warehouse__name', 'warehouse__code']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    """Admin for ProductCategory model."""
    list_display = ['name', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model."""
    list_display = ['sku', 'name', 'category', 'unit_of_measure', 'initial_stock', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['sku', 'name', 'category__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'category')
        }),
        ('Stock Information', {
            'fields': ('unit_of_measure', 'initial_stock', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReorderRule)
class ReorderRuleAdmin(admin.ModelAdmin):
    """Admin for ReorderRule model."""
    list_display = ['product', 'warehouse', 'min_quantity', 'max_quantity', 'created_at']
    list_filter = ['warehouse', 'created_at']
    search_fields = ['product__sku', 'product__name', 'warehouse__name', 'warehouse__code']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


class StockMoveLineInline(admin.TabularInline):
    """Inline admin for StockMoveLine."""
    model = StockMoveLine
    extra = 1
    readonly_fields = ['created_at', 'updated_at']
    fields = ['product', 'quantity', 'created_at']


@admin.register(StockDocument)
class StockDocumentAdmin(admin.ModelAdmin):
    """Admin for StockDocument model."""
    list_display = ['id', 'doc_type', 'status', 'reference', 'contact_name', 'created_by', 'scheduled_date', 'created_at']
    list_filter = ['doc_type', 'status', 'created_at', 'scheduled_date']
    search_fields = ['reference', 'contact_name', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at', 'validated_at']
    date_hierarchy = 'created_at'
    inlines = [StockMoveLineInline]
    fieldsets = (
        ('Document Information', {
            'fields': ('doc_type', 'status', 'reference', 'created_by')
        }),
        ('Contact Information', {
            'fields': ('contact_name', 'delivery_address')
        }),
        ('Location Information', {
            'fields': ('source_location', 'destination_location')
        }),
        ('Schedule', {
            'fields': ('scheduled_date', 'validated_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StockMoveLine)
class StockMoveLineAdmin(admin.ModelAdmin):
    """Admin for StockMoveLine model."""
    list_display = ['id', 'document', 'product', 'quantity', 'created_at']
    list_filter = ['document__doc_type', 'created_at']
    search_fields = ['document__reference', 'product__sku', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(StockQuant)
class StockQuantAdmin(admin.ModelAdmin):
    """Admin for StockQuant model."""
    list_display = ['product', 'location', 'quantity', 'created_at']
    list_filter = ['location__warehouse', 'created_at']
    search_fields = ['product__sku', 'product__name', 'location__code', 'location__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    """Admin for StockLedgerEntry model."""
    list_display = ['id', 'document', 'product', 'source_location', 'destination_location', 'quantity_delta', 'created_at']
    list_filter = ['document__doc_type', 'created_at']
    search_fields = ['document__reference', 'product__sku', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
