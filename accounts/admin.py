from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PasswordResetOTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with role field."""
    list_display = ['username', 'email', 'role', 'first_name', 'last_name', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    """Admin for Password Reset OTP."""
    list_display = ['user', 'otp', 'is_used', 'created_at', 'expires_at', 'is_valid']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'otp']
    readonly_fields = ['otp', 'created_at', 'expires_at']
    date_hierarchy = 'created_at'
    
    def is_valid(self, obj):
        """Display if OTP is still valid."""
        return obj.is_valid() if obj.pk else False
    is_valid.boolean = True
    is_valid.short_description = 'Is Valid'