"""
Custom decorators for API endpoints that return JSON instead of HTML redirects
"""
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

def api_login_required(view_func):
    """
    API version of login_required that returns JSON 401 instead of HTML redirect
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'authenticated': False
            }, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

