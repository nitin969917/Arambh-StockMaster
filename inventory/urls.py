from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("warehouses/", views.warehouse_list, name="warehouse_list"),
    path("warehouses/new/", views.warehouse_create, name="warehouse_create"),
    path("locations/new/", views.location_create, name="location_create"),
    path("operations/", views.operations_list, name="operations_list"),
    path("operations/deliveries/", views.delivery_operations, name="delivery_operations"),
    path("stock/", views.stock_list, name="stock_list"),
    path("receipts/new/", views.receipt_create, name="receipt_create"),
    path("deliveries/new/", views.delivery_create, name="delivery_create"),
    path("deliveries/<int:pk>/", views.delivery_detail, name="delivery_detail"),
    path("deliveries/<int:pk>/edit/", views.delivery_edit, name="delivery_edit"),
    path("deliveries/<int:pk>/validate/", views.delivery_validate, name="delivery_validate"),
    path("deliveries/<int:pk>/cancel/", views.delivery_cancel, name="delivery_cancel"),
    path("deliveries/<int:pk>/print/", views.delivery_print, name="delivery_print"),
    path("transfers/new/", views.internal_transfer_create, name="internal_transfer_create"),
    path("adjustments/new/", views.stock_adjustment_create, name="stock_adjustment_create"),
    path("move-history/", views.move_history, name="move_history"),
    path("settings/", views.settings_view, name="settings"),
]



