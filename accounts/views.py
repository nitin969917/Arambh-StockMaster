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
            user = form.save(commit=False)
            # Default role to warehouse_staff for public signups
            user.role = User.Roles.WAREHOUSE_STAFF
            user.save()
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


def logout_view(request):
    """Custom logout view to ensure proper redirection"""
    from django.contrib.auth import logout
    logout(request)
    from django.contrib import messages
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


def password_reset_request(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data["identifier"]
            user = (
                User.objects.filter(username=identifier).first()
                or User.objects.filter(email=identifier).first()
            )
            if user:
                from django.core.mail import send_mail
                from django.conf import settings
                
                otp_obj = PasswordResetOTP.create_otp_for_user(user)
                otp_code = otp_obj.otp
                
                # Send OTP via email
                try:
                    email_subject = 'StockMaster - Password Reset OTP'
                    email_message = f'''Hello {user.username},

You have requested to reset your password for StockMaster IMS.

Your OTP (One-Time Password) is: {otp_code}

This OTP is valid for 10 minutes. Please use it to reset your password at:
http://127.0.0.1:8000/accounts/password-reset/verify/

If you did not request this password reset, please ignore this email.

Best regards,
StockMaster Team'''
                    
                    send_mail(
                        subject=email_subject,
                        message=email_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    messages.success(
                        request,
                        f"An OTP has been sent to your email address ({user.email}). Please check your inbox.",
                    )
                except Exception as e:
                    # Log the error but don't expose full error to user
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send password reset email: {str(e)}")
                    messages.error(
                        request,
                        f"Failed to send email. Please contact support or try again later. (OTP for testing: {otp_code})",
                    )
                return redirect("accounts:password_reset_verify")
            else:
                messages.error(request, "User not found for given identifier.")
    else:
        form = PasswordResetRequestForm()
    return render(
        request,
        "accounts/password_reset_request.html",
        {"form": form},
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

