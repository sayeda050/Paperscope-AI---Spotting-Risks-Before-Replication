from pathlib import Path
import os
import environ

# ---------------------------------------------------------
# Env setup
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # -> backend/
env = environ.Env(
    DJANGO_DEBUG=(bool, True),
)
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------
# Core settings
# ---------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-change-me-later")
DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Frontend url used for password reset links
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# ---------------------------------------------------------
# Apps
# ---------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "apps.users",
    "apps.papers",
    "apps.analysis",
    "apps.logs_app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# ---------------------------------------------------------
# Database
# ---------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

# ---------------------------------------------------------
# Auth
# ---------------------------------------------------------
AUTH_USER_MODEL = "users.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# ---------------------------------------------------------
# DRF + JWT cookies
# ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "paperscope-auth",
    "JWT_AUTH_REFRESH_COOKIE": "paperscope-refresh-token",
    "REGISTER_SERIALIZER": "apps.users.serializers.CustomRegisterSerializer",
}

SIMPLE_JWT = {
    "USER_ID_FIELD": "user_id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------
# allauth (use ONE style consistently)
# ---------------------------------------------------------
# New-style settings (keep these)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"

# Google OAuth
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID"),
            "secret": env("GOOGLE_SECRET"),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "VERIFIED_EMAIL": True,
    }
}

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# ---------------------------------------------------------
# Static / Media
# ---------------------------------------------------------
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------
# i18n
# ---------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------
# CORS / CSRF / Cookies
# ---------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False