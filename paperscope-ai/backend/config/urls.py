from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse(
        {
            "name": "PaperScope AI Backend",
            "version": "v1",
            "status": "ok",
        }
    )


urlpatterns = [
    path("", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("dj_rest_auth.urls")),
    path("api/auth/registration/", include("dj_rest_auth.registration.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/papers/", include("apps.papers.urls")),
    path("api/analysis/", include("apps.analysis.urls")),
    path("api/analysis/models/", include("apps.analysis.model_registry_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)