from django.urls import path

from .model_registry_views import (
    AdminModelListView,
    AdminModelActivateView,
    AdminModelRefreshView,
    ActiveModelDetailView,
    ActiveModelPredictView,
)

urlpatterns = [
    path("models/", AdminModelListView.as_view(), name="admin-model-list"),
    path("models/activate/", AdminModelActivateView.as_view(), name="admin-model-activate"),
    path("models/refresh/", AdminModelRefreshView.as_view(), name="admin-model-refresh"),
    path("models/active/", ActiveModelDetailView.as_view(), name="active-model-detail"),
    path("models/predict/", ActiveModelPredictView.as_view(), name="active-model-predict"),
]