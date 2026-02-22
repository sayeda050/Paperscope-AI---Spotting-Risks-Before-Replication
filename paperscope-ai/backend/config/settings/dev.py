from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# React dev server (Vite default)
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

# In dev, allow unauthenticated access to docs endpoints if needed
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = (
    "rest_framework.permissions.IsAuthenticated",
)

# Email is printed to terminal in dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# If you want Django to accept requests from your phone (same WiFi)
# ALLOWED_HOSTS = ["127.0.0.1", "localhost", "<YOUR_PC_LOCAL_IP>"]