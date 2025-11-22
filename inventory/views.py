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

    document.status = StockDocument.Status.DONE
    document.save(update_fields=["status"])


@login_required
def dashboard(request):
    """
    Dashboard view. Warehouse staff only see data from their assigned warehouse.
    Inventory managers see all data.
    """
    from django.utils import timezone
    
    # Filter by warehouse for warehouse staff
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff: only their warehouse's stock - use ID for strict comparison
        total_stock = (
            StockQuant.objects.filter(location__warehouse_id=user_warehouse_id)
            .aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        )
        
        # Low stock alerts based on Product.low_stock_alert field
        low_stock_items = []
        products_with_stock = Product.objects.filter(is_active=True).prefetch_related('quants')
        
        for product in products_with_stock:
            total_at_warehouse = (
                StockQuant.objects.filter(
                    product=product, location__warehouse_id=user_warehouse_id
                ).aggregate(total=Sum("quantity"))["total"]
                or Decimal("0")
            )
            # Check if stock is below low_stock_alert threshold
            if product.low_stock_alert > 0 and total_at_warehouse <= product.low_stock_alert:
                low_stock_items.append({
                    'product': product,
                    'warehouse': request.user.warehouse,
                    'quantity': total_at_warehouse,
                    'threshold': product.low_stock_alert,
                    'is_out_of_stock': total_at_warehouse == 0
                })

        today = timezone.now().date()

        # Warehouse staff see ONLY operations within their warehouse
        user_warehouse_id = request.user.warehouse.id
        
        # Receipts: Only those coming INTO their warehouse
        receipts_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.RECEIPT,
            destination_location__warehouse_id=user_warehouse_id
        )
        # Deliveries: Only those going OUT FROM their warehouse
        deliveries_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.DELIVERY,
            source_location__warehouse_id=user_warehouse_id
        )
        # Internal transfers: BOTH source AND destination must be in their warehouse
        internal_transfers_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.INTERNAL,
            source_location__warehouse_id=user_warehouse_id,
            destination_location__warehouse_id=user_warehouse_id
        )
    else:
        # Inventory managers: all data
        total_stock = (
            StockQuant.objects.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        )

        # Low stock alerts based on Product.low_stock_alert field
        low_stock_items = []
        products_with_stock = Product.objects.filter(is_active=True).prefetch_related('quants')
        warehouses = Warehouse.objects.all()
        
        for warehouse in warehouses:
            for product in products_with_stock:
                total_at_warehouse = (
                    StockQuant.objects.filter(
                        product=product, location__warehouse=warehouse
                    ).aggregate(total=Sum("quantity"))["total"]
                    or Decimal("0")
                )
                # Check if stock is below low_stock_alert threshold
                if product.low_stock_alert > 0 and total_at_warehouse <= product.low_stock_alert:
                    low_stock_items.append({
                        'product': product,
                        'warehouse': warehouse,
                        'quantity': total_at_warehouse,
                        'threshold': product.low_stock_alert,
                        'is_out_of_stock': total_at_warehouse == 0
                    })

        today = timezone.now().date()

        # Filter documents by current user
        receipts_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.RECEIPT,
            created_by=request.user
        )
        deliveries_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by=request.user
        )
        internal_transfers_qs = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.INTERNAL,
            created_by=request.user
        )

    # Open operations (not done or canceled)
    open_statuses = [
        StockDocument.Status.DRAFT,
        StockDocument.Status.WAITING,
        StockDocument.Status.READY,
    ]

    receipt_open = receipts_qs.filter(status__in=open_statuses)
    delivery_open = deliveries_qs.filter(status__in=open_statuses)
    internal_transfers_open = internal_transfers_qs.filter(status__in=open_statuses)

    context = {
        "total_stock": total_stock,
        "low_stock_items": low_stock_items,
        # Receipt KPIs (filtered by user)
        "receipt_to_receive": receipt_open.count(),
        "receipt_late": receipt_open.filter(scheduled_date__lt=today).count(),
        "receipt_waiting": receipt_open.filter(status=StockDocument.Status.WAITING).count(),
        "receipt_operations": receipts_qs.count(),
        # Delivery KPIs (filtered by user)
        "delivery_to_deliver": delivery_open.count(),
        "delivery_late": delivery_open.filter(scheduled_date__lt=today).count(),
        "delivery_waiting": delivery_open.filter(status=StockDocument.Status.WAITING).count(),
        "delivery_operations": deliveries_qs.count(),
        # Internal Transfers (filtered by user)
        "internal_transfers": internal_transfers_open.count(),
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
            # Note: initial_stock is just a field on the product model.
            # Actual stock (StockQuant) should be created when products are received via Receipt.
            # We don't automatically create StockQuant entries here to avoid cross-warehouse issues.
            # StockQuant entries are created location-specific when receipts are processed.
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
    from accounts.models import User
    
    if request.method == "POST":
        form = WarehouseForm(request.POST)
        if form.is_valid():
            # Create warehouse
            warehouse = form.save()
            
            # Create user for warehouse with warehouse_staff role
            username = form.cleaned_data.get("user_username")
            email = form.cleaned_data.get("user_email")
            password = form.cleaned_data.get("user_password1")
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=User.Roles.WAREHOUSE_STAFF,
                warehouse=warehouse  # Assign warehouse to user
            )
            
            messages.success(
                request, 
                f"Warehouse '{warehouse.name}' created successfully. "
                f"Warehouse staff account '{username}' has been created."
            )
            return redirect("inventory:settings")
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
    """
    Operations list view. Warehouse staff only see operations related to their warehouse.
    Inventory managers see all operations they created.
    """
    # Filter by warehouse for warehouse staff
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff see ONLY operations within their warehouse
        # For receipts: destination must be in their warehouse
        # For deliveries: source must be in their warehouse
        # For internal transfers: BOTH source AND destination must be in their warehouse
        documents = StockDocument.objects.select_related(
            "source_location__warehouse", "destination_location__warehouse", "created_by"
        ).filter(
            Q(
                # Receipts: destination in user's warehouse
                doc_type=StockDocument.DocTypes.RECEIPT,
                destination_location__warehouse_id=user_warehouse_id
            ) | Q(
                # Deliveries: source in user's warehouse
                doc_type=StockDocument.DocTypes.DELIVERY,
                source_location__warehouse_id=user_warehouse_id
            ) | Q(
                # Internal transfers: BOTH source AND destination in user's warehouse
                doc_type=StockDocument.DocTypes.INTERNAL,
                source_location__warehouse_id=user_warehouse_id,
                destination_location__warehouse_id=user_warehouse_id
            )
        )
        warehouses = Warehouse.objects.filter(id=user_warehouse_id)
    else:
        # Inventory managers see operations they created
        documents = StockDocument.objects.select_related(
            "source_location__warehouse", "destination_location__warehouse", "created_by"
        ).filter(created_by=request.user)
        warehouses = Warehouse.objects.all()

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
        form = ReceiptForm(request.POST, user=request.user)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Additional validation for warehouse staff
            if request.user.is_warehouse_staff() and request.user.warehouse:
                destination_location = form.cleaned_data.get('destination_location')
                if destination_location and destination_location.warehouse_id != request.user.warehouse.id:
                    form.add_error('destination_location', f'You can only receive into locations in your assigned warehouse ({request.user.warehouse.name}).')
                    formset = StockMoveLineFormSet(request.POST)
                    return form, formset
            
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
        form = ReceiptForm(user=request.user)
        formset = StockMoveLineFormSet()
        # Don't set default quantity - it will be auto-populated by JavaScript based on product's initial_stock
    return form, formset


def _handle_delivery_create(request):
    """Handle delivery creation with customer information (external destination)."""
    if request.method == "POST":
        form = DeliveryForm(request.POST, user=request.user)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Additional validation for warehouse staff
            if request.user.is_warehouse_staff() and request.user.warehouse:
                source_location = form.cleaned_data.get('source_location')
                if source_location and source_location.warehouse_id != request.user.warehouse.id:
                    form.add_error('source_location', f'You can only ship from locations in your assigned warehouse ({request.user.warehouse.name}).')
                    formset = StockMoveLineFormSet(request.POST)
                    return form, formset
            
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
        form = DeliveryForm(user=request.user)
        formset = StockMoveLineFormSet()
    return form, formset


def _handle_document_create(request, doc_type):
    """Handle document creation for internal transfers (both source and destination are internal)."""
    from django.utils import timezone
    
    if request.method == "POST":
        form = StockDocumentBaseForm(request.POST, user=request.user)
        formset = StockMoveLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Additional validation: Ensure warehouse staff can only transfer within their warehouse
            if request.user.is_warehouse_staff() and request.user.warehouse:
                user_warehouse_id = request.user.warehouse.id
                source_location = form.cleaned_data.get('source_location')
                destination_location = form.cleaned_data.get('destination_location')
                
                # Strict validation: Both locations must be in user's warehouse
                if source_location:
                    if source_location.warehouse_id != user_warehouse_id:
                        form.add_error('source_location', f'You can only transfer from locations in your assigned warehouse ({request.user.warehouse.name}).')
                        formset = StockMoveLineFormSet(request.POST)
                        return form, formset
                
                if destination_location:
                    if destination_location.warehouse_id != user_warehouse_id:
                        form.add_error('destination_location', f'You can only transfer to locations in your assigned warehouse ({request.user.warehouse.name}).')
                        formset = StockMoveLineFormSet(request.POST)
                        return form, formset
                
                # For internal transfers, both must be in the same warehouse (user's warehouse)
                if doc_type == StockDocument.DocTypes.INTERNAL:
                    if source_location and destination_location:
                        if source_location.warehouse_id != user_warehouse_id or destination_location.warehouse_id != user_warehouse_id:
                            form.add_error(None, 'Internal transfers must be within your assigned warehouse only.')
                            formset = StockMoveLineFormSet(request.POST)
                            return form, formset
            
            document = form.save(commit=False)
            document.doc_type = doc_type
            document.created_by = request.user
            document.status = StockDocument.Status.DRAFT
            document.save()
            formset.instance = document
            formset.save()
            
            # Auto-validate internal transfers if scheduled_date is today or in the past
            if doc_type == StockDocument.DocTypes.INTERNAL:
                today = timezone.now().date()
                if document.scheduled_date and document.scheduled_date <= today:
                    validate_document(document)
                    messages.success(request, f"Internal transfer created and validated. Stock updated.")
                else:
                    messages.success(request, f"Internal transfer created in Draft status.")
            else:
                messages.success(request, f"{doc_type.capitalize()} created.")
            return redirect("inventory:operations_list")
    else:
        form = StockDocumentBaseForm(user=request.user)
        formset = StockMoveLineFormSet()
    return form, formset


@inventory_manager_required
def receipt_create(request):
    result = _handle_receipt_create(request)
    # If result is a redirect response, return it directly
    if hasattr(result, 'status_code'):
        return result
    # Otherwise, unpack form and formset
    form, formset = result
    # Make quantity fields readonly in the formset for receipts
    for line_form in formset.forms:
        if 'quantity' in line_form.fields:
            line_form.fields['quantity'].widget.attrs['readonly'] = True
            line_form.fields['quantity'].widget.attrs['class'] = 'form-control bg-light receipt-quantity'
            line_form.fields['quantity'].widget.attrs['style'] = 'cursor: not-allowed;'
        # Hide delete checkbox for receipts
        if 'DELETE' in line_form.fields:
            line_form.fields['DELETE'].widget = line_form.fields['DELETE'].hidden_widget()
    
    # Get products with their initial_stock for JavaScript
    from .models import Product
    import json
    products_data = {
        str(product.id): float(product.initial_stock) if product.initial_stock else 0
        for product in Product.objects.all()
    }
    
    return render(
        request,
        "inventory/document_form.html",
        {
            "form": form, 
            "formset": formset, 
            "title": "New Receipt (Incoming from Vendor)", 
            "is_receipt": True,
            "products_initial_stock": json.dumps(products_data),
        },
    )


@inventory_manager_required
def delivery_create(request):
    result = _handle_delivery_create(request)
    # If result is a redirect response, return it directly
    if hasattr(result, 'status_code'):
        return result
    # Otherwise, unpack form and formset
    form, formset = result
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Delivery Order (Outgoing to Customer)", "is_receipt": False},
    )


@warehouse_staff_required
def internal_transfer_create(request):
    result = _handle_document_create(request, StockDocument.DocTypes.INTERNAL)
    # If result is a redirect response, return it directly
    if hasattr(result, 'status_code'):
        return result
    # Otherwise, unpack form and formset
    form, formset = result
    return render(
        request,
        "inventory/document_form.html",
        {"form": form, "formset": formset, "title": "New Internal Transfer", "is_receipt": False},
    )


@login_required
def move_history(request):
    """
    Move history view. Warehouse staff only see moves related to their warehouse.
    Inventory managers see all moves they created.
    """
    # Filter by warehouse for warehouse staff
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff see ONLY moves within their warehouse
        # Receipts: destination_location must be in their warehouse
        # Deliveries: source_location must be in their warehouse
        # Internal transfers: BOTH source AND destination must be in their warehouse
        queryset = StockLedgerEntry.objects.select_related(
            "product", "source_location__warehouse", "destination_location__warehouse", "document__created_by"
        ).filter(
            Q(
                # Receipts: destination in user's warehouse
                document__doc_type=StockDocument.DocTypes.RECEIPT,
                destination_location__warehouse_id=user_warehouse_id
            ) | Q(
                # Deliveries: source in user's warehouse
                document__doc_type=StockDocument.DocTypes.DELIVERY,
                source_location__warehouse_id=user_warehouse_id
            ) | Q(
                # Internal transfers: BOTH source AND destination in user's warehouse
                document__doc_type=StockDocument.DocTypes.INTERNAL,
                source_location__warehouse_id=user_warehouse_id,
                destination_location__warehouse_id=user_warehouse_id
            )
        ).order_by("-created_at")
    else:
        # Inventory managers see moves from documents they created
        queryset = StockLedgerEntry.objects.select_related(
            "product", "source_location__warehouse", "destination_location__warehouse", "document__created_by"
        ).filter(document__created_by=request.user).order_by("-created_at")

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
    Warehouse staff only see stock from their assigned warehouse.
    """
    # Filter by warehouse for warehouse staff - strict filtering
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Only show stock from user's warehouse - use ID for strict comparison
        quants = StockQuant.objects.select_related("product", "location__warehouse").filter(
            location__warehouse_id=user_warehouse_id
        )
        warehouses = Warehouse.objects.filter(id=user_warehouse_id)
        locations = Location.objects.filter(warehouse_id=user_warehouse_id)
    else:
        # Inventory managers see all warehouses
        quants = StockQuant.objects.select_related("product", "location__warehouse").all()
        warehouses = Warehouse.objects.all()
        locations = Location.objects.all()

    warehouse_id = request.GET.get("warehouse")
    location_id = request.GET.get("location")
    sku = request.GET.get("sku")

    if warehouse_id:
        quants = quants.filter(location__warehouse_id=warehouse_id)
    if location_id:
        quants = quants.filter(location_id=location_id)
    if sku:
        quants = quants.filter(product__sku__icontains=sku)

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
    For warehouse staff: show deliveries from warehouses created by inventory managers.
    For inventory managers: show deliveries created by themselves.
    """
    from accounts.models import User
    
    # Different filtering logic for warehouse staff vs inventory managers
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff: show ONLY deliveries FROM their warehouse created by inventory managers
        documents = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by__role=User.Roles.INVENTORY_MANAGER,  # Only inventory manager created deliveries
            source_location__warehouse_id=user_warehouse_id  # Only from their warehouse
        ).select_related(
            "source_location__warehouse", "destination_location__warehouse", "created_by"
        )
    else:
        # Inventory managers: show only their own deliveries
        documents = StockDocument.objects.filter(
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by=request.user
        ).select_related(
            "source_location__warehouse", "destination_location__warehouse", "created_by"
        )

    reference = request.GET.get("reference")
    contact = request.GET.get("contact")
    status = request.GET.get("status")
    warehouse_id = request.GET.get("warehouse")
    view_mode = request.GET.get("view", "list")

    # Only filter if values are provided (not empty strings)
    if reference:
        documents = documents.filter(reference__icontains=reference)
    if contact:
        documents = documents.filter(contact_name__icontains=contact)
    if status:
        documents = documents.filter(status=status)
    if warehouse_id:
        # Filter by warehouse (source_location's warehouse for deliveries)
        documents = documents.filter(source_location__warehouse_id=warehouse_id)

    # Get warehouses for filter dropdown
    warehouses = Warehouse.objects.all()

    return render(
        request,
        "inventory/delivery_operations.html",
        {
            "documents": documents.order_by("-created_at"),
            "selected_reference": reference,
            "selected_contact": contact,
            "selected_status": status,
            "selected_warehouse": warehouse_id,
            "warehouses": warehouses,
            "status_choices": StockDocument.Status.choices,
            "view_mode": view_mode,
        },
    )


@login_required
def delivery_detail(request, pk):
    """
    Detail view for a single delivery document, showing lines and stock availability.
    """
    # Filter by warehouse for warehouse staff, by created_by for inventory managers
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff can only view deliveries FROM their warehouse
        doc = get_object_or_404(
            StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
            pk=pk,
            doc_type=StockDocument.DocTypes.DELIVERY,
            source_location__warehouse_id=user_warehouse_id,  # Only from their warehouse
        )
    else:
        # Inventory managers can view their own deliveries
        doc = get_object_or_404(
            StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
            pk=pk,
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by=request.user,  # Filter by current user
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
    # Warehouse staff can only validate deliveries FROM their warehouse
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        doc = get_object_or_404(
            StockDocument, 
            pk=pk, 
            doc_type=StockDocument.DocTypes.DELIVERY,
            source_location__warehouse_id=user_warehouse_id,  # Only from their warehouse
        )
    else:
        # Fallback (shouldn't happen due to decorator, but just in case)
        doc = get_object_or_404(
            StockDocument, 
            pk=pk, 
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by=request.user,
        )
    validate_document(doc)
    messages.success(request, "Delivery validated and stock updated.")
    return redirect("inventory:delivery_detail", pk=pk)


@inventory_manager_required
def delivery_edit(request, pk):
    """
    Edit an existing delivery: header info and product lines (Add new product).
    """
    # Ensure user can only edit their own documents
    doc = get_object_or_404(
        StockDocument,
        pk=pk,
        doc_type=StockDocument.DocTypes.DELIVERY,
        created_by=request.user,  # Filter by current user
    )
    if request.method == "POST":
        form = DeliveryForm(request.POST, instance=doc, user=request.user)
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
        form = DeliveryForm(instance=doc, user=request.user)
        formset = StockMoveLineFormSet(instance=doc)

    return render(
        request,
        "inventory/document_form.html",
        {
            "form": form,
            "formset": formset,
            "title": f"Edit Delivery {doc.reference}",
            "is_receipt": False,
        },
    )


@inventory_manager_required
def delivery_cancel(request, pk):
    """
    Cancel a delivery: mark status as Canceled (no stock movement if not yet done).
    Only Inventory Managers can cancel deliveries.
    """
    # Ensure user can only cancel their own documents
    doc = get_object_or_404(
        StockDocument, 
        pk=pk, 
        doc_type=StockDocument.DocTypes.DELIVERY,
        created_by=request.user,  # Filter by current user
    )
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
    # Filter by warehouse for warehouse staff, by created_by for inventory managers
    if request.user.is_warehouse_staff() and request.user.warehouse:
        user_warehouse_id = request.user.warehouse.id
        # Warehouse staff can only print deliveries FROM their warehouse
        doc = get_object_or_404(
            StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
            pk=pk,
            doc_type=StockDocument.DocTypes.DELIVERY,
            source_location__warehouse_id=user_warehouse_id,  # Only from their warehouse
        )
    else:
        # Inventory managers can print their own deliveries
        doc = get_object_or_404(
            StockDocument.objects.select_related("source_location__warehouse", "destination_location__warehouse"),
            pk=pk,
            doc_type=StockDocument.DocTypes.DELIVERY,
            created_by=request.user,  # Filter by current user
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

