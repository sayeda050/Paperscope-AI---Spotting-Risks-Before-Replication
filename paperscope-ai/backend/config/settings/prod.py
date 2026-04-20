from .base import *  # noqa: F401, F403
import os

# ---------------------------------------------------------
# Core
# ---------------------------------------------------------
DEBUG = False

# ALLOWED_HOSTS is loaded from env in base.py via _env_list().
# Set this in Render dashboard:
#   ALLOWED_HOSTS=your-backend.onrender.com

# ---------------------------------------------------------
# SSL / Proxy
# Render terminates SSL at their load balancer and forwards to your app
# over HTTP with X-Forwarded-Proto: https. This tells Django to trust
# that header so it recognises the request as HTTPS.
# ---------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# ---------------------------------------------------------
# Cookies — MUST be SameSite=None for cross-origin setup
# Your frontend (Vercel) and backend (Render) are on different domains.
# SameSite=None + Secure=True is required for cookies to be sent cross-site.
# FIX: Original prod.py set Secure=True but forgot SameSite=None —
# this would silently break JWT cookie auth for every user in production.
# ---------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# ---------------------------------------------------------
# CORS / CSRF — production domains
# Set these in Render dashboard:
#   CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app,capacitor://localhost
#   CSRF_TRUSTED_ORIGINS=https://your-frontend.vercel.app
# _env_list() in base.py parses these comma-separated strings automatically.
# ---------------------------------------------------------
# (already loaded from env in base.py — no need to repeat them here)

# ---------------------------------------------------------
# Email — real SMTP in production
# Set EMAIL_HOST_USER, EMAIL_HOST_PASSWORD in Render dashboard.
# Using standard Django SMTP backend (not the certifi custom one from dev).
# ---------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "no-reply@paperscope.app"

# ---------------------------------------------------------
# Cloudinary — persistent media storage
# Render free tier has an ephemeral filesystem. Without Cloudinary, every
# redeploy wipes uploaded PDFs. When CLOUDINARY_CLOUD_NAME is set in the
# Render dashboard, media files go to Cloudinary instead of local disk.
# ---------------------------------------------------------
_cloudinary_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
if _cloudinary_name:
    INSTALLED_APPS = INSTALLED_APPS + [  # type: ignore[name-defined]
        "cloudinary",
        "cloudinary_storage",
    ]
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": _cloudinary_name,
        "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
        "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
        "SECURE": True,
    }
    STORAGES["default"] = {  # type: ignore[name-defined]
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }

# ---------------------------------------------------------
# Logging — surface errors in Render log stream
# ---------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
