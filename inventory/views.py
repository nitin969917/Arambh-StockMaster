from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import inventory_manager_required, warehouse_staff_required
from .forms import (
    DeliveryForm,
    LocationForm,
    ProductForm,
    ReceiptForm,
    StockDocumentBaseForm,
    StockMoveLineFormSet,
    WarehouseForm,
)
from .models import (
    Location,
    Product,
    ProductCategory,
    ReorderRule,
    StockDocument,
    StockLedgerEntry,
    StockQuant,
    Warehouse,
)


def _update_quant(product, location, delta: Decimal):
    quant, _ = StockQuant.objects.get_or_create(product=product, location=location)
    quant.quantity = quant.quantity + Decimal(delta)
    quant.save()


def _create_ledger_entry(document, product, source_location, destination_location, delta):
    StockLedgerEntry.objects.create(
        document=document,
        product=product,
        source_location=source_location,
        destination_location=destination_location,
        quantity_delta=delta,
    )


@transaction.atomic
def validate_document(document: StockDocument):
    if document.status == StockDocument.Status.DONE:
        return

    for line in document.lines.all():
        qty = line.quantity
        if document.doc_type == StockDocument.DocTypes.RECEIPT:
            dest = document.destination_location
            _update_quant(line.product, dest, qty)
            _create_ledger_entry(document, line.product, None, dest, qty)
        elif document.doc_type == StockDocument.DocTypes.DELIVERY:
            src = document.source_location
            _update_quant(line.product, src, -qty)
            _create_ledger_entry(document, line.product, src, None, -qty)
        elif document.doc_type == StockDocument.DocTypes.INTERNAL:
            src = document.source_location
            dest = document.destination_location
            _update_quant(line.product, src, -qty)
            _update_quant(line.product, dest, qty)
            _create_ledger_entry(document, line.product, src, dest, qty)
        elif document.doc_type == StockDocument.DocTypes.ADJUSTMENT:
            # For adjustments we treat quantity as delta directly on destination_location
            loc = document.destination_location or document.source_location
            _update_quant(line.product, loc, qty)
            _create_ledger_entry(document, line.product, None, loc, qty)

    document.status = StockDocument.Status.DONE
    document.save(update_fields=["status"])


@login_required
def dashboard(request):
    total_stock = (
        StockQuant.objects.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
    )

    low_stock_rules = ReorderRule.objects.all()
    low_stock_items = []
    for rule in low_stock_rules:
        total_at_warehouse = (
            StockQuant.objects.filter(
                product=rule.product, location__warehouse=rule.warehouse
            ).aggregate(total=Sum("quantity"))["total"]
            or Decimal("0")
        )
        if total_at_warehouse <= rule.min_quantity:
            low_stock_items.append((rule, total_at_warehouse))

    from django.utils import timezone

    today = timezone.now().date()

    receipts_qs = StockDocument.objects.filter(doc_type=StockDocument.DocTypes.RECEIPT)
    deliveries_qs = StockDocument.objects.filter(doc_type=StockDocument.DocTypes.DELIVERY)

    # Open operations (not done or canceled)
    open_statuses = [
        StockDocument.Status.DRAFT,
        StockDocument.Status.WAITING,
        StockDocument.Status.READY,
    ]

    receipt_open = receipts_qs.filter(status__in=open_statuses)
    delivery_open = deliveries_qs.filter(status__in=open_statuses)

    context = {
        "total_stock": total_stock,
        "low_stock_items": low_stock_items,
        # Receipt KPIs
        "receipt_to_receive": receipt_open.count(),
        "receipt_late": receipt_open.filter(scheduled_date__lt=today).count(),
        "receipt_waiting": receipt_open.filter(status=StockDocument.Status.WAITING).count(),
        "receipt_operations": receipts_qs.count(),
        # Delivery KPIs
        "delivery_to_deliver": delivery_open.count(),
        "delivery_late": delivery_open.filter(scheduled_date__lt=today).count(),
        "delivery_waiting": delivery_open.filter(status=StockDocument.Status.WAITING).count(),
        "delivery_operations": deliveries_qs.count(),
    }
    return render(request, "inventory/dashboard.html", context)


@inventory_manager_required
def product_list(request):
    products = Product.objects.select_related("category").all()
    categories = ProductCategory.objects.all()
    selected_category = request.GET.get("category")
    if selected_category:
        products = products.filter(category_id=selected_category)
    return render(
        request,
        "inventory/product_list.html",
        {"products": products, "categories": categories, "selected_category": selected_category},
    )


@inventory_manager_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, "Product created.")
            # If initial stock > 0, create quant in default location if available
            initial = form.cleaned_data.get("initial_stock") or Decimal("0")
            if initial > 0:
                default_location = Location.objects.filter(is_default=True).first()
                if default_location:
                    _update_quant(product, default_location, initial)
            return redirect("inventory:product_list")
    else:
        form = ProductForm()
    return render(request, "inventory/product_form.html", {"form": form})


@inventory_manager_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "inventory/product_form.html", {"form": form, "product": product})


@inventory_manager_required
def warehouse_list(request):
    warehouses = Warehouse.objects.all()
    return render(request, "inventory/warehouse_list.html", {"warehouses": warehouses})


@inventory_manager_required
def warehouse_create(request):
    if request.method == "POST":
        form = WarehouseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Warehouse created.")
            return redirect("inventory:warehouse_list")
    else:
        form = WarehouseForm()
    return render(request, "inventory/warehouse_form.html", {"form": form})


@inventory_manager_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Location created.")
            return redirect("inventory:warehouse_list")
    else:
        form = LocationForm()
    return render(request, "inventory/location_form.html", {"form": form})


@login_required
def operations_list(request):
    documents = StockDocument.objects.select_related(
        "source_location__warehouse", "destination_location__warehouse"
    ).all()

    doc_type = request.GET.get("doc_type")
    status = request.GET.get("status")
    warehouse_id = request.GET.get("warehouse")

    if doc_type:
        documents = documents.filter(doc_type=doc_type)
    if status:
        documents = documents.filter(status=status)
    if warehouse_id:
        documents = documents.filter(
            Q(source_location__warehouse_id=warehouse_id)
            | Q(destination_location__warehouse_id=warehouse_id)
        )

    warehouses = Warehouse.objects.all()

    return render(
        request,
        "inventory/operations_list.html",
        {
            "documents": documents.order_by("-created_at"),
            "warehouses": warehouses,
            "selected_doc_type": doc_type,
            "selected_status": status,
            "selected_warehouse": warehouse_id,
            "status_choices": StockDocument.Status.choices,
            "doc_type_choices": StockDocument.DocTypes.choices,
        },
    )


def _handle_receipt_create(request):
    """Handle receipt creation with vendor information (external source)."""
    if request.method == "POST":
        form = ReceiptForm(request.POST)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            document = form.save(commit=False)
            document.doc_type = StockDocument.DocTypes.RECEIPT
            document.created_by = request.user
            document.source_location = None  # Receipt comes from external vendor
            document.status = StockDocument.Status.READY
            document.save()
            formset.instance = document
            formset.save()
            validate_document(document)
            messages.success(request, "Receipt created and stock updated.")
            return redirect("inventory:operations_list")
    else:
        form = ReceiptForm()
        formset = StockMoveLineFormSet()
    return form, formset


def _handle_delivery_create(request):
    """Handle delivery creation with customer information (external destination)."""
    if request.method == "POST":
        form = DeliveryForm(request.POST)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            document = form.save(commit=False)
            document.doc_type = StockDocument.DocTypes.DELIVERY
            document.created_by = request.user
            document.destination_location = None  # Delivery goes to external customer
            document.status = StockDocument.Status.DRAFT
            document.save()
            formset.instance = document
            formset.save()
            messages.success(request, "Delivery created in Draft status.")
            return redirect("inventory:delivery_detail", pk=document.pk)
    else:
        form = DeliveryForm()
        formset = StockMoveLineFormSet()
    return form, formset


@inventory_manager_required
def receipt_create(request):
    form, formset = _handle_receipt_create(request)
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Receipt (Incoming from Vendor)"},
    )


@inventory_manager_required
def delivery_create(request):
    form, formset = _handle_delivery_create(request)
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Delivery Order (Outgoing to Customer)"},
    )


@warehouse_staff_required
def internal_transfer_create(request):
    form, formset = _handle_document_create(request, StockDocument.DocTypes.INTERNAL)
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Internal Transfer"},
    )


@warehouse_staff_required
def stock_adjustment_create(request):
    """
    Simplified adjustment: user selects destination location and lines where quantity is delta.
    """
    if request.method == "POST":
        form = StockDocumentBaseForm(request.POST)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            document = form.save(commit=False)
            document.doc_type = StockDocument.DocTypes.ADJUSTMENT
            document.created_by = request.user
            document.status = StockDocument.Status.READY
            document.save()
            formset.instance = document
            formset.save()
            validate_document(document)
            messages.success(request, "Stock adjustment applied.")
            return redirect("inventory:operations_list")
    else:
        form = StockDocumentBaseForm()
        formset = StockMoveLineFormSet()
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Stock Adjustment"},
    )


@login_required
def move_history(request):
    queryset = StockLedgerEntry.objects.select_related(
        "product", "source_location__warehouse", "destination_location__warehouse", "document"
    ).order_by("-created_at")

    doc_type = request.GET.get("doc_type")
    if doc_type:
        queryset = queryset.filter(document__doc_type=doc_type)

    product_sku = request.GET.get("sku")
    if product_sku:
        queryset = queryset.filter(product__sku__icontains=product_sku)

    reference = request.GET.get("reference")
    if reference:
        queryset = queryset.filter(document__reference__icontains=reference)

    contact = request.GET.get("contact")
    if contact:
        queryset = queryset.filter(document__contact_name__icontains=contact)

    view_mode = request.GET.get("view", "list")

    return render(
        request,
        "inventory/move_history.html",
        {
            "entries": queryset[:200],
            "doc_type_choices": StockDocument.DocTypes.choices,
            "status_choices": StockDocument.Status.choices,
            "selected_doc_type": doc_type,
            "selected_sku": product_sku,
            "selected_reference": reference,
            "selected_contact": contact,
            "view_mode": view_mode,
        },
    )


@login_required
def stock_list(request):
    """
    Lists available stock per product/location with simple filters.
    """
    quants = StockQuant.objects.select_related("product", "location__warehouse").all()

    warehouse_id = request.GET.get("warehouse")
    location_id = request.GET.get("location")
    sku = request.GET.get("sku")

    if warehouse_id:
        quants = quants.filter(location__warehouse_id=warehouse_id)
    if location_id:
        quants = quants.filter(location_id=location_id)
    if sku:
        quants = quants.filter(product__sku__icontains=sku)

    warehouses = Warehouse.objects.all()
    locations = Location.objects.all()

    return render(
        request,
        "inventory/stock_list.html",
        {
            "quants": quants.order_by("product__sku"),
            "warehouses": warehouses,
            "locations": locations,
            "selected_warehouse": warehouse_id,
            "selected_location": location_id,
            "selected_sku": sku,
        },
    )


@inventory_manager_required
def settings_view(request):
    """
    Simple settings page listing warehouses and locations with shortcuts to create new ones.
    """
    warehouses = Warehouse.objects.prefetch_related("locations").all()
    return render(
        request,
        "inventory/settings.html",
        {
            "warehouses": warehouses,
        },
    )


@login_required
def delivery_operations(request):
    """
    List view for Delivery operations only, with search and kanban toggle.
    """
    documents = StockDocument.objects.filter(doc_type=StockDocument.DocTypes.DELIVERY).select_related(
        "source_location__warehouse", "destination_location__warehouse"
    )

    reference = request.GET.get("reference")
    contact = request.GET.get("contact")
    status = request.GET.get("status")
    view_mode = request.GET.get("view", "list")

    if reference:
        documents = documents.filter(reference__icontains=reference)
    if contact:
        documents = documents.filter(contact_name__icontains=contact)
    if status:
        documents = documents.filter(status=status)

    return render(
        request,
        "inventory/delivery_operations.html",
        {
            "documents": documents.order_by("-created_at"),
            "selected_reference": reference,
            "selected_contact": contact,
            "selected_status": status,
            "status_choices": StockDocument.Status.choices,
            "view_mode": view_mode,
        },
    )


@login_required
def delivery_detail(request, pk):
    """
    Detail view for a single delivery document, showing lines and stock availability.
    """
    doc = get_object_or_404(
        StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
        pk=pk,
        doc_type=StockDocument.DocTypes.DELIVERY,
    )
    lines = list(doc.lines.select_related("product"))

    # Compute available qty at source for each product (for highlighting shortages)
    line_infos = []
    any_short = False
    for line in lines:
        available = (
            StockQuant.objects.filter(
                product=line.product, location=doc.source_location
            ).aggregate(total=Sum("quantity"))["total"]
            or Decimal("0")
        )
        is_short = available < line.quantity
        if is_short:
            any_short = True
        line_infos.append({"line": line, "available": available, "is_short": is_short})

    # Update status automatically based on availability flow:
    # Draft -> Waiting (if shortages) or Ready (if fully available).
    if doc.status in (StockDocument.Status.DRAFT, StockDocument.Status.WAITING, StockDocument.Status.READY):
        new_status = None
        if any_short:
            new_status = StockDocument.Status.WAITING
        else:
            new_status = StockDocument.Status.READY
        if new_status and new_status != doc.status:
            doc.status = new_status
            doc.save(update_fields=["status"])

    return render(
        request,
        "inventory/delivery_detail.html",
        {
            "document": doc,
            "line_infos": line_infos,
            "status_choices": StockDocument.Status.choices,
        },
    )


@warehouse_staff_required
def delivery_validate(request, pk):
    """
    Trigger validation of a delivery document and move stock.
    Warehouse staff can execute/validate deliveries.
    """
    doc = get_object_or_404(StockDocument, pk=pk, doc_type=StockDocument.DocTypes.DELIVERY)
    validate_document(doc)
    messages.success(request, "Delivery validated and stock updated.")
    return redirect("inventory:delivery_detail", pk=pk)


@inventory_manager_required
def delivery_edit(request, pk):
    """
    Edit an existing delivery: header info and product lines (Add new product).
    """
    doc = get_object_or_404(StockDocument, pk=pk, doc_type=StockDocument.DocTypes.DELIVERY)
    if request.method == "POST":
        form = DeliveryForm(request.POST, instance=doc)
        formset = StockMoveLineFormSet(request.POST, instance=doc)
        if form.is_valid() and formset.is_valid():
            form.save()
            # Ensure destination_location remains None for external deliveries
            doc.destination_location = None
            doc.save()
            formset.save()
            messages.success(request, "Delivery updated.")
            return redirect("inventory:delivery_detail", pk=pk)
    else:
        form = DeliveryForm(instance=doc)
        formset = StockMoveLineFormSet(instance=doc)

    return render(
        request,
        "inventory/document_form.html",
        {
            "form": form,
            "formset": formset,
            "title": f"Edit Delivery {doc.reference}",
        },
    )


@inventory_manager_required
def delivery_cancel(request, pk):
    """
    Cancel a delivery: mark status as Canceled (no stock movement if not yet done).
    Only Inventory Managers can cancel deliveries.
    """
    doc = get_object_or_404(StockDocument, pk=pk, doc_type=StockDocument.DocTypes.DELIVERY)
    if doc.status != StockDocument.Status.DONE:
        doc.status = StockDocument.Status.CANCELED
        doc.save(update_fields=["status"])
        messages.success(request, "Delivery canceled.")
    else:
        messages.info(request, "Completed deliveries cannot be canceled.")
    return redirect("inventory:delivery_detail", pk=pk)


@login_required
def delivery_print(request, pk):
    """
    Simple print-friendly page for a delivery. Browser print dialog can be used.
    """
    doc = get_object_or_404(
        StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
        pk=pk,
        doc_type=StockDocument.DocTypes.DELIVERY,
    )
    lines = doc.lines.select_related("product")
    return render(
        request,
        "inventory/delivery_print.html",
        {
            "document": doc,
            "lines": lines,
        },
    )

