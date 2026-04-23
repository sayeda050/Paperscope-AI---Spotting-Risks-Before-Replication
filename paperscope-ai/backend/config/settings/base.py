from pathlib import Path
import os

import cloudinary
import environ

# ---------------------------------------------------------
# Paths / env
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # -> backend/

env = environ.Env(
    DJANGO_DEBUG=(bool, True),
)

# FIX 1: Guard added. Original called read_env() unconditionally.
# On Render there is no .env file — environment vars come from the dashboard.
# Without this guard, startup raises FileNotFoundError on Render.
_env_file = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_env_file):
    environ.Env.read_env(_env_file)


# FIX 2: _env_list() helper added.
# prod.py needs this to parse comma-separated env vars like:
#   ALLOWED_HOSTS=my-app.onrender.com,localhost
# Without it, prod.py raises NameError at import time and Django never starts.
def _env_list(name, default=None):
    if default is None:
        default = []
    raw_value = env(name, default="")
    if not raw_value:
        return list(default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


# ---------------------------------------------------------
# Cloudinary global SDK config (preserved from your version)
# ---------------------------------------------------------
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME", default="")
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET", default="")

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

# ---------------------------------------------------------
# Core
# ---------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-change-me-later")
DEBUG = env.bool("DJANGO_DEBUG", default=True)

# FIX 3: ALLOWED_HOSTS is now env-driven.
# Original hardcoded ["127.0.0.1", "localhost"] — every Render request gets
# a 400 Bad Request because the Render domain is not in the list.
ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"],
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Frontend URL used for password reset links and Google OAuth callback.
# .rstrip("/") prevents double-slash bugs in URL construction.
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173").rstrip("/")

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

# ---------------------------------------------------------
# Middleware
# ---------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # FIX 4: WhiteNoiseMiddleware added directly after SecurityMiddleware.
    # Required for serving compressed static files on Render.
    # Without this, static files are missing and the admin panel is unstyled.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# FIX 5: DATABASE_URL path added.
# Neon provides a single connection string. Original only supported DB_* vars.
# Now: DATABASE_URL takes priority; DB_* vars work as fallback for local dev.
# Your existing local .env (with DB_NAME, DB_USER etc.) still works unchanged.
# PGSSLMODE preserved from your version — Neon requires sslmode=require.
# ---------------------------------------------------------
DATABASE_URL = env("DATABASE_URL", default="").strip()

if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
    db_sslmode = env("PGSSLMODE", default="")
    if db_sslmode:
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"]["sslmode"] = db_sslmode
else:
    db_options = {}
    db_sslmode = env("PGSSLMODE", default="")
    if db_sslmode:
        db_options["sslmode"] = db_sslmode

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT", default="5432"),
            "OPTIONS": db_options,
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
    # Base defaults — dev.py and prod.py override these
    "JWT_AUTH_SECURE": False,
    "JWT_AUTH_SAMESITE": "Lax",
    "REGISTER_SERIALIZER": "apps.users.serializers.CustomRegisterSerializer",
    "USER_DETAILS_SERIALIZER": "apps.users.serializers.UserSerializer",
}

SIMPLE_JWT = {
    "USER_ID_FIELD": "user_id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------
# allauth — preserved exactly from your working version
# ---------------------------------------------------------
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"

# Old-style compat settings kept from your original
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            # Reads GOOGLE_SECRET (your .env name) with GOOGLE_CLIENT_SECRET
            # as fallback so both naming conventions work.
            "secret": env(
                "GOOGLE_SECRET",
                default=env("GOOGLE_CLIENT_SECRET", default=""),
            ),
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
# FIX 6: STATIC_ROOT added — without it `collectstatic` raises ImproperlyConfigured.
# FIX 7: STORAGES dict added — prod.py writes STORAGES["default"] = Cloudinary;
#         without this dict existing, that line raises NameError at import time.
# ---------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        # Local dev uses filesystem. prod.py switches this to Cloudinary.
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # WhiteNoise compresses + fingerprints static files for production.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------
# i18n
# ---------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------
# CORS / CSRF / Cookies
# FIX 8 & 9: Were hardcoded lists — Vercel domain blocked in production.
# Now reads from env with safe local dev defaults.
# Set CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS in Render dashboard.
# Local dev still works identically — the defaults kick in automatically.
# ---------------------------------------------------------
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)

CORS_ALLOW_CREDENTIALS = True

# Base defaults — dev.py and prod.py override these explicitly
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ---------------------------------------------------------
# Password validators
# ---------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
