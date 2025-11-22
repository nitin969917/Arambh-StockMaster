from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    LoginForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    SignUpForm,
)
from .models import PasswordResetOTP, User


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created. You can now log in.")
            return redirect("accounts:login")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("inventory:dashboard")
    else:
        form = LoginForm(request)
    return render(request, "accounts/login.html", {"form": form})


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


def password_reset_request(request):
    otp_code = None
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data["identifier"]
            user = (
                User.objects.filter(username=identifier).first()
                or User.objects.filter(email=identifier).first()
            )
            if user:
                otp_obj = PasswordResetOTP.create_otp_for_user(user)
                otp_code = otp_obj.otp  # For demo purposes we show OTP on screen.
                messages.info(
                    request,
                    "An OTP has been generated. In production this would be sent via email/SMS.",
                )
            else:
                messages.error(request, "User not found for given identifier.")
    else:
        form = PasswordResetRequestForm()
    return render(
        request,
        "accounts/password_reset_request.html",
        {"form": form, "otp_code": otp_code},
    )


def password_reset_verify(request):
    if request.method == "POST":
        form = PasswordResetVerifyForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data["identifier"]
            otp = form.cleaned_data["otp"]
            user = (
                User.objects.filter(username=identifier).first()
                or User.objects.filter(email=identifier).first()
            )
            if not user:
                messages.error(request, "User not found.")
            else:
                otp_obj = (
                    PasswordResetOTP.objects.filter(user=user, otp=otp, is_used=False)
                    .order_by("-created_at")
                    .first()
                )
                if not otp_obj or not otp_obj.is_valid():
                    messages.error(request, "Invalid or expired OTP.")
                else:
                    user.set_password(form.cleaned_data["new_password1"])
                    user.save()
                    otp_obj.is_used = True
                    otp_obj.save(update_fields=["is_used"])
                    messages.success(request, "Password updated. You can now log in.")
                    return redirect("accounts:login")
    else:
        form = PasswordResetVerifyForm()
    return render(request, "accounts/password_reset_verify.html", {"form": form})

