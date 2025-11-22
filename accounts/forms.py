from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


def validate_password_strength(password: str):
    import re

    if len(password) <= 8:
        raise forms.ValidationError("Password must be longer than 8 characters.")
    if not re.search(r"[a-z]", password):
        raise forms.ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"[A-Z]", password):
        raise forms.ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise forms.ValidationError("Password must contain at least one special character.")


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "role", "password1", "password2")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not (6 <= len(username) <= 12):
            raise forms.ValidationError("Login ID must be between 6 and 12 characters.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()  # runs UserCreationForm validation incl. password match
        password2 = cleaned.get("password2")
        if password2:
            validate_password_strength(password2)
        return cleaned


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Login Id")

    error_messages = {
        "invalid_login": "Invalid Login Id or Password",
        "inactive": "This account is inactive.",
    }


class PasswordResetRequestForm(forms.Form):
    identifier = forms.CharField(
        label="Username or Email",
        max_length=150,
        help_text="Enter your username or email to receive an OTP.",
    )


class PasswordResetVerifyForm(forms.Form):
    identifier = forms.CharField(label="Username or Email", max_length=150)
    otp = forms.CharField(label="OTP", max_length=6)
    new_password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        pwd1 = cleaned.get("new_password1")
        pwd2 = cleaned.get("new_password2")
        if pwd1 and pwd2 and pwd1 != pwd2:
            self.add_error("new_password2", "Passwords do not match.")
        if pwd1:
            validate_password_strength(pwd1)
        return cleaned

