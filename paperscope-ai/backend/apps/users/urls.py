from django.urls import path, include
from .views import MeView, GoogleLogin

urlpatterns = [
    # Logged-in user profile
    path("me/", MeView.as_view(), name="user-me"),

    # Frontend calls this after getting Google token
    path("google/", GoogleLogin.as_view(), name="google_login"),

    # Forgot/reset password endpoints
    path("", include("apps.users.auth_urls")),
]