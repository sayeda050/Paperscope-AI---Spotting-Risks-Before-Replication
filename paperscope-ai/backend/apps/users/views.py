from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        # Returning your specific custom user fields — unchanged from original
        return Response({
            "user_id": u.user_id,
            "username": u.username,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": u.role,
            "created_at": u.created_at,
        })


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    # FIX: was hardcoded "http://localhost:5173" — that causes Google OAuth to
    # redirect to localhost even in production. Now uses FRONTEND_URL from env,
    # which is http://localhost:5173 in dev and your Vercel URL in production.
    callback_url = settings.FRONTEND_URL
    client_class = OAuth2Client
