from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def inventory_manager_required(view_func):
    """
    Decorator to restrict access to Inventory Managers only.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_inventory_manager():
            messages.error(request, "Access denied. This function is restricted to Inventory Managers.")
            return redirect('inventory:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def warehouse_staff_required(view_func):
    """
    Decorator to restrict access to Warehouse Staff only.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_warehouse_staff():
            messages.error(request, "Access denied. This function is restricted to Warehouse Staff.")
            return redirect('inventory:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

