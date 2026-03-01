from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()
token_generator = PasswordResetTokenGenerator()


class ForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()

        # Always return success (prevents leaking whether email exists)
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)

            frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

            subject = "Reset your PaperScope AI password"
            message = (
                "We received a request to reset your password.\n\n"
                f"Reset link:\n{reset_link}\n\n"
                "If you did not request this, ignore this email."
            )
            print("SENDING RESET EMAIL VIA:", settings.EMAIL_BACKEND, settings.EMAIL_HOST, settings.EMAIL_HOST_USER)
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

        return Response(
            {"detail": "If an account exists for that email, a reset link has been sent."},
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        uid = request.data.get("uid") or ""
        token = request.data.get("token") or ""
        new_password = request.data.get("new_password") or ""

        if not uid or not token or not new_password:
            return Response(
                {"detail": "uid, token, and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return Response({"detail": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        if len(new_password) < 8:
            return Response({"detail": "Password must be at least 8 characters."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"detail": "Password reset successful. Please log in."}, status=status.HTTP_200_OK)