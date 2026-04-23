from .base import *  # noqa: F401, F403
import os

# ---------------------------------------------------------
# Core
# ---------------------------------------------------------
DEBUG = False

# ---------------------------------------------------------
# SSL / Proxy
# Render terminates SSL at the load balancer and sets X-Forwarded-Proto: https.
# Without SECURE_PROXY_SSL_HEADER, Django sees plain HTTP and SECURE_SSL_REDIRECT
# causes an infinite redirect loop.
# ---------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# ---------------------------------------------------------
# Cookies — MUST be SameSite=None for cross-origin setup.
# Frontend (Vercel) and backend (Render) are on different domains.
# SameSite=None + Secure=True is required for cookies to be sent cross-site.
# SameSite=Lax (the base default) silently blocks every JWT cookie in production.
# ---------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# JWT cookies must also be cross-site
REST_AUTH = {**REST_AUTH, "JWT_AUTH_SECURE": True, "JWT_AUTH_SAMESITE": "None"}  # noqa: F405

# ---------------------------------------------------------
# CORS / CSRF — set via Render dashboard env vars.
# _env_list() in base.py parses comma-separated strings automatically.
# Render dashboard values:
#   CORS_ALLOWED_ORIGINS = https://your-frontend.vercel.app,capacitor://localhost
#   CSRF_TRUSTED_ORIGINS = https://your-frontend.vercel.app,https://your-backend.onrender.com
# No need to redefine here — base.py already reads them from env.
# ---------------------------------------------------------

# ---------------------------------------------------------
# Email — standard Django SMTP (not the certifi custom backend from dev)
# Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in Render dashboard.
# ---------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@paperscope.app"
)

# ---------------------------------------------------------
# Cloudinary — persistent media storage.
# Render free tier has an ephemeral filesystem — uploaded files are wiped on
# every redeploy/restart. Cloudinary provides persistent storage.
# Activated only when CLOUDINARY_CLOUD_NAME is set in Render dashboard.
# base.py already called cloudinary.config() if credentials are set.
# ---------------------------------------------------------
_cloudinary_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
if _cloudinary_name:
    # Guard against double-adding if base.py already included them
    if "cloudinary" not in INSTALLED_APPS:  # noqa: F405
        INSTALLED_APPS = list(INSTALLED_APPS) + [  # noqa: F405
            "cloudinary",
            "cloudinary_storage",
        ]

    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": _cloudinary_name,
        "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
        "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
        "SECURE": True,
    }

    # STORAGES is defined in base.py — safe to mutate here
    STORAGES = {**STORAGES, "default": {  # noqa: F405
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }}

# ---------------------------------------------------------
# Logging — surfaces errors in Render log stream
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
