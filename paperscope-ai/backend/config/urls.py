from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


# --------------------------------------------------
# Root / Health Check
# --------------------------------------------------
def health(request):
    return JsonResponse({
        "status": "ok",
        "service": "PaperScope AI Backend",
        "version": "v1"
    })


# --------------------------------------------------
# URL Configuration
# --------------------------------------------------
urlpatterns = [
    # Root health check
    path("", health, name="health"),

    # Django admin
    path("admin/", admin.site.urls),

    # --- 1. ADDED THIS LINE TO FIX THE GOOGLE CRASH ---
    path('accounts/', include('allauth.urls')), 

    # Authentication (dj-rest-auth)
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),

    # Application APIs
    path("api/users/", include("apps.users.urls")),
    path("api/papers/", include("apps.papers.urls")),
    path("api/analysis/", include("apps.analysis.urls")),
]


# --------------------------------------------------
# Media files (DEV only)
# --------------------------------------------------
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )