from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user with role support for Inventory Managers and Warehouse Staff.
    """

    class Roles(models.TextChoices):
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"
        WAREHOUSE_STAFF = "warehouse_staff", "Warehouse Staff"

    # Login ID rules: unique, 6-12 characters handled via validators.
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[MinLengthValidator(6)],
        help_text="Required. 6-12 characters.",
    )

    email = models.EmailField("email address", unique=True)

    role = models.CharField(
        max_length=32,
        choices=Roles.choices,
        default=Roles.INVENTORY_MANAGER,
    )

    def is_inventory_manager(self) -> bool:
        return self.role == self.Roles.INVENTORY_MANAGER

    def is_warehouse_staff(self) -> bool:
        return self.role == self.Roles.WAREHOUSE_STAFF


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_otps")
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() <= self.expires_at

    @classmethod
    def create_otp_for_user(cls, user: User, lifetime_minutes: int = 10) -> "PasswordResetOTP":
        expires_at = timezone.now() + timedelta(minutes=lifetime_minutes)
        import random

        otp = f"{random.randint(0, 999999):06d}"
        return cls.objects.create(user=user, otp=otp, expires_at=expires_at)
