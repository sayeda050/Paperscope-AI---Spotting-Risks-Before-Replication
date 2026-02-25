from django.urls import path
from .views import MeView, GoogleLogin

urlpatterns = [
    # This is for fetching the logged-in user's profile info
    path('me/', MeView.as_view(), name='user-me'),
    
    # This is the endpoint the frontend calls after getting a Google token
    path('google/', GoogleLogin.as_view(), name='google_login'),
]