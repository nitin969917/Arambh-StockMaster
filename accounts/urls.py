from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/verify/", views.password_reset_verify, name="password_reset_verify"),
]



