from django.urls import path
from .views_password_reset import ForgotPasswordView, ResetPasswordView

urlpatterns = [
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]