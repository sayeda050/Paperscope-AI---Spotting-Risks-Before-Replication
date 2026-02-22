from .base import *  # noqa

DEBUG = False

# IMPORTANT: set ALLOWED_HOSTS in .env for production
# Example: ALLOWED_HOSTS=your-render-domain.onrender.com
# base.py already loads ALLOWED_HOSTS from env.

# Security hardening (minimum)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# You can keep CORS_ALLOWED_ORIGINS in env and load here if needed
# For now, define later during deployment.