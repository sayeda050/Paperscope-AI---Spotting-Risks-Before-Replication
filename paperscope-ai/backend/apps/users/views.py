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
    # Uses FRONTEND_URL from env:
    #   dev  → http://localhost:5173
    #   prod → your deployed Vercel URL
    callback_url = settings.FRONTEND_URL
    client_class = OAuth2Client
