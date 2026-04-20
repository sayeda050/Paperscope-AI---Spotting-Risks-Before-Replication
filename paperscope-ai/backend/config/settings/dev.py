from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Explicit local CORS/CSRF (same as base defaults, kept here for clarity)
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

# Cookie settings for local dev (http is fine locally)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------
# Email (SMTP - Gmail) using certifi CA bundle
# Your custom backend — preserved exactly as original
# --------------------------------------------------
EMAIL_BACKEND = "apps.users.email_backend.CertifiEmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")          # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")  # noqa: F405
