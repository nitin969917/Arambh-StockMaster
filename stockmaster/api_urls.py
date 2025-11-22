"""
API URLs for Django REST API endpoints
This file creates API endpoints that the Next.js frontend can consume
"""
from django.urls import path
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
import json
from stockmaster.api_decorators import api_login_required
from inventory.models import (
    Product, ProductCategory, StockDocument, StockLedgerEntry, StockQuant,
    Warehouse, Location, StockMoveLine
)
from django.db.models import Sum, Q
from decimal import Decimal

@ensure_csrf_cookie
@csrf_exempt
def csrf_token_view(request):
    """Return CSRF token for API requests"""
    from django.middleware.csrf import get_token
    get_token(request)
    token = request.COOKIES.get('csrftoken', '')
    response = JsonResponse({'csrfToken': token})
    return response

@csrf_exempt
def login_api(request):
    """Login API endpoint that returns JSON"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        username = data.get('username', '')
        password = data.get('password', '')
        
        if not username or not password:
            return JsonResponse({'error': 'Username and password are required'}, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                    }
                })
            else:
                return JsonResponse({'error': 'Account is inactive'}, status=403)
        else:
            return JsonResponse({'error': 'Invalid Login ID or Password'}, status=401)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def logout_api(request):
    """Logout API endpoint"""
    from django.contrib.auth import logout
    if request.user.is_authenticated:
        logout(request)
    return JsonResponse({'success': True})

@csrf_exempt
def current_user_api(request):
    """Get current authenticated user"""
    # Check if user is authenticated
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'email': request.user.email,
                'role': request.user.role,
            }
        })
    else:
        # Return 200 with authenticated: false instead of 401
        # This prevents the error from being treated as a failure
        return JsonResponse({'authenticated': False})

@csrf_exempt
def signup_api(request):
    """Signup API endpoint that returns JSON"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        from accounts.forms import SignUpForm
        
        form = SignUpForm(data)
        if form.is_valid():
            user = form.save()
            # Auto-login after signup
            login(request, user)
            return JsonResponse({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                },
                'message': 'Account created successfully'
            })
        else:
            # Return form errors
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0] if field_errors else ''
            return JsonResponse({
                'success': False,
                'error': 'Validation failed',
                'errors': errors
            }, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@api_login_required
def dashboard_api(request):
    """Dashboard KPIs API"""
    from datetime import date
    
    today = date.today()
    
    # Total stock
    total_stock = StockQuant.objects.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    
    # Low stock items
    from inventory.models import ReorderRule
    low_stock_items = []
    for rule in ReorderRule.objects.select_related('product', 'warehouse'):
        qty = StockQuant.objects.filter(
            product=rule.product,
            location__warehouse=rule.warehouse
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        if qty <= rule.min_quantity:
            low_stock_items.append({
                'rule': {
                    'id': rule.id,
                    'product': {'id': rule.product.id, 'name': rule.product.name, 'sku': rule.product.sku},
                    'warehouse': {'id': rule.warehouse.id, 'name': rule.warehouse.name},
                    'min_quantity': float(rule.min_quantity),
                },
                'qty': float(qty)
            })
    
    # Stock by category
    stock_by_category = []
    for category in ProductCategory.objects.all():
        total = StockQuant.objects.filter(
            product__category=category
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        if total > 0:
            stock_by_category.append({
                'category': category.name,
                'quantity': float(total),
            })
    
    # Calculate percentages
    total_for_percentage = sum(item['quantity'] for item in stock_by_category)
    if total_for_percentage > 0:
        for item in stock_by_category:
            item['percentage'] = round((item['quantity'] / total_for_percentage) * 100, 1)
    
    # Pending receipts
    receipt_to_receive = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.RECEIPT,
        status__in=['draft', 'waiting', 'ready']
    ).count()
    receipt_late = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.RECEIPT,
        scheduled_date__lt=today,
        status__in=['draft', 'waiting', 'ready']
    ).count()
    receipt_operations = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.RECEIPT
    ).count()
    
    # Pending deliveries
    delivery_to_deliver = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.DELIVERY,
        status__in=['draft', 'waiting', 'ready']
    ).count()
    delivery_late = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.DELIVERY,
        scheduled_date__lt=today,
        status__in=['draft', 'waiting', 'ready']
    ).count()
    delivery_waiting = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.DELIVERY,
        status='waiting'
    ).count()
    delivery_operations = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.DELIVERY
    ).count()
    
    # Internal transfers
    internal_transfers = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.INTERNAL,
        status__in=['draft', 'waiting', 'ready']
    ).count()
    
    return JsonResponse({
        'total_stock': float(total_stock),
        'low_stock_items': low_stock_items,
        'stock_by_category': stock_by_category,
        'receipt_to_receive': receipt_to_receive,
        'receipt_late': receipt_late,
        'receipt_operations': receipt_operations,
        'delivery_to_deliver': delivery_to_deliver,
        'delivery_late': delivery_late,
        'delivery_waiting': delivery_waiting,
        'delivery_operations': delivery_operations,
        'internal_transfers': internal_transfers,
    })

@csrf_exempt
@api_login_required
def products_api(request):
    """Products list API"""
    products = Product.objects.select_related('category').all()
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    return JsonResponse({
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'sku': p.sku,
                'category': p.category.name if p.category else None,
                'unit_of_measure': p.unit_of_measure,
                'is_active': p.is_active,
            }
            for p in products
        ],
        'categories': [
            {'id': c.id, 'name': c.name}
            for c in ProductCategory.objects.all()
        ]
    })

@csrf_exempt
@api_login_required
def create_product_api(request):
    """Create product API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        from inventory.forms import ProductForm
        
        form = ProductForm(data)
        if form.is_valid():
            product = form.save()
            return JsonResponse({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else None,
                'unit_of_measure': product.unit_of_measure,
                'is_active': product.is_active,
            })
        return JsonResponse({'errors': form.errors}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
@api_login_required
def update_product_api(request, product_id):
    """Update product API"""
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        product = Product.objects.get(id=product_id)
        data = json.loads(request.body)
        from inventory.forms import ProductForm
        
        form = ProductForm(data, instance=product)
        if form.is_valid():
            product = form.save()
            return JsonResponse({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else None,
                'unit_of_measure': product.unit_of_measure,
                'is_active': product.is_active,
            })
        return JsonResponse({'errors': form.errors}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
@api_login_required
def receipts_api(request):
    """Receipts list API"""
    receipts = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.RECEIPT
    ).select_related('destination_location', 'created_by').order_by('-created_at')
    
    status = request.GET.get('status')
    if status:
        receipts = receipts.filter(status=status)
    
    return JsonResponse({
        'receipts': [
            {
                'id': r.id,
                'reference': r.reference,
                'contact_name': r.contact_name,
                'destination_location': r.destination_location.name if r.destination_location else None,
                'scheduled_date': r.scheduled_date.isoformat() if r.scheduled_date else None,
                'status': r.status,
                'created_at': r.created_at.isoformat(),
            }
            for r in receipts
        ]
    })

@csrf_exempt
@api_login_required
def create_receipt_api(request):
    """Create receipt API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        from inventory.forms import ReceiptForm
        
        form = ReceiptForm(data, user=request.user)
        if form.is_valid():
            receipt = form.save()
            return JsonResponse({
                'id': receipt.id,
                'reference': receipt.reference,
                'contact_name': receipt.contact_name,
                'destination_location': receipt.destination_location.name if receipt.destination_location else None,
                'scheduled_date': receipt.scheduled_date.isoformat() if receipt.scheduled_date else None,
                'status': receipt.status,
            })
        return JsonResponse({'errors': form.errors}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
@api_login_required
def deliveries_api(request):
    """Deliveries list API"""
    deliveries = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.DELIVERY
    ).select_related('source_location', 'created_by').order_by('-created_at')
    
    reference = request.GET.get('reference')
    contact = request.GET.get('contact')
    status = request.GET.get('status')
    
    if reference:
        deliveries = deliveries.filter(reference__icontains=reference)
    if contact:
        deliveries = deliveries.filter(contact_name__icontains=contact)
    if status:
        deliveries = deliveries.filter(status=status)
    
    return JsonResponse({
        'deliveries': [
            {
                'id': d.id,
                'reference': d.reference,
                'source_location': d.source_location.name if d.source_location else None,
                'contact_name': d.contact_name,
                'delivery_address': d.delivery_address,
                'scheduled_date': d.scheduled_date.isoformat() if d.scheduled_date else None,
                'status': d.status,
                'created_at': d.created_at.isoformat(),
            }
            for d in deliveries
        ]
    })

@csrf_exempt
@api_login_required
def transfers_api(request):
    """Internal transfers list API"""
    transfers = StockDocument.objects.filter(
        doc_type=StockDocument.DocTypes.INTERNAL
    ).select_related('source_location', 'destination_location', 'created_by').order_by('-created_at')
    
    return JsonResponse({
        'transfers': [
            {
                'id': t.id,
                'reference': t.reference,
                'source_location': t.source_location.name if t.source_location else None,
                'destination_location': t.destination_location.name if t.destination_location else None,
                'scheduled_date': t.scheduled_date.isoformat() if t.scheduled_date else None,
                'status': t.status,
                'created_at': t.created_at.isoformat(),
            }
            for t in transfers
        ]
    })

@csrf_exempt
@api_login_required
def create_transfer_api(request):
    """Create internal transfer API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        from inventory.forms import StockDocumentBaseForm
        
        form = StockDocumentBaseForm(data, user=request.user)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.doc_type = StockDocument.DocTypes.INTERNAL
            transfer.save()
            return JsonResponse({
                'id': transfer.id,
                'reference': transfer.reference,
                'source_location': transfer.source_location.name if transfer.source_location else None,
                'destination_location': transfer.destination_location.name if transfer.destination_location else None,
                'scheduled_date': transfer.scheduled_date.isoformat() if transfer.scheduled_date else None,
                'status': transfer.status,
            })
        return JsonResponse({'errors': form.errors}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
@api_login_required
def move_history_api(request):
    """Move history API"""
    entries = StockLedgerEntry.objects.select_related(
        'product', 'source_location__warehouse', 'destination_location__warehouse', 'document'
    ).order_by('-created_at')
    
    doc_type = request.GET.get('doc_type')
    reference = request.GET.get('reference')
    contact = request.GET.get('contact')
    sku = request.GET.get('sku')
    
    if doc_type:
        entries = entries.filter(document__doc_type=doc_type)
    if reference:
        entries = entries.filter(document__reference__icontains=reference)
    if contact:
        entries = entries.filter(document__contact_name__icontains=contact)
    if sku:
        entries = entries.filter(product__sku__icontains=sku)
    
    return JsonResponse({
        'entries': [
            {
                'id': e.id,
                'document': {
                    'reference': e.document.reference,
                    'contact_name': e.document.contact_name,
                    'status': e.document.status,
                },
                'product': {
                    'id': e.product.id,
                    'sku': e.product.sku,
                    'name': e.product.name,
                },
                'source_location': e.source_location.name if e.source_location else None,
                'destination_location': e.destination_location.name if e.destination_location else None,
                'quantity_delta': float(e.quantity_delta),
                'created_at': e.created_at.isoformat(),
            }
            for e in entries
        ]
    })

@csrf_exempt
@api_login_required
def warehouses_api(request):
    """Warehouses API"""
    warehouses = Warehouse.objects.prefetch_related('locations').all()
    return JsonResponse({
        'warehouses': [
            {
                'id': w.id,
                'name': w.name,
                'code': w.code,
                'address': w.address,
                'locations': [
                    {
                        'id': l.id,
                        'code': l.code,
                        'name': l.name,
                        'is_default': l.is_default,
                    }
                    for l in w.locations.all()
                ]
            }
            for w in warehouses
        ]
    })

@csrf_exempt
@api_login_required
def categories_api(request):
    """Categories API"""
    return JsonResponse({
        'categories': [
            {'id': c.id, 'name': c.name}
            for c in ProductCategory.objects.all()
        ]
    })

@csrf_exempt
@api_login_required
def locations_api(request):
    """Locations API"""
    return JsonResponse({
        'locations': [
            {
                'id': l.id,
                'name': l.name,
                'code': l.code,
                'warehouse': l.warehouse.name,
                'warehouse_id': l.warehouse.id,
            }
            for l in Location.objects.select_related('warehouse').all()
        ]
    })

urlpatterns = [
    path('csrf-token/', csrf_token_view, name='api_csrf_token'),
    path('login/', login_api, name='api_login'),
    path('logout/', logout_api, name='api_logout'),
    path('signup/', signup_api, name='api_signup'),
    path('current-user/', current_user_api, name='api_current_user'),
    path('dashboard/', dashboard_api, name='api_dashboard'),
    path('products/', products_api, name='api_products'),
    path('products/create/', create_product_api, name='api_create_product'),
    path('products/<int:product_id>/', update_product_api, name='api_update_product'),
    path('receipts/', receipts_api, name='api_receipts'),
    path('receipts/create/', create_receipt_api, name='api_create_receipt'),
    path('deliveries/', deliveries_api, name='api_deliveries'),
    path('transfers/', transfers_api, name='api_transfers'),
    path('transfers/create/', create_transfer_api, name='api_create_transfer'),
    path('move-history/', move_history_api, name='api_move_history'),
    path('warehouses/', warehouses_api, name='api_warehouses'),
    path('categories/', categories_api, name='api_categories'),
    path('locations/', locations_api, name='api_locations'),
]
