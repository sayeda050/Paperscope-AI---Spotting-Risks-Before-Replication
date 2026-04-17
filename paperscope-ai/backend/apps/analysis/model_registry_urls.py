from django.urls import path

from .model_registry_views import (
    AdminModelActivateView,
    AdminModelListView,
    AdminModelRefreshView,
    ActiveModelDetailView,
    ActiveModelPredictView,
)

urlpatterns = [
    # Primary routes used by the current frontend.
    path("", AdminModelListView.as_view(), name="admin-model-list"),
    path("activate/", AdminModelActivateView.as_view(), name="admin-model-activate"),
    path("refresh/", AdminModelRefreshView.as_view(), name="admin-model-refresh"),
    path("active/", ActiveModelDetailView.as_view(), name="active-model-detail"),
    path("predict/", ActiveModelPredictView.as_view(), name="active-model-predict"),

    # Backward-compatible legacy routes.
    path("models/", AdminModelListView.as_view(), name="admin-model-list-legacy"),
    path("models/activate/", AdminModelActivateView.as_view(), name="admin-model-activate-legacy"),
    path("models/refresh/", AdminModelRefreshView.as_view(), name="admin-model-refresh-legacy"),
    path("models/active/", ActiveModelDetailView.as_view(), name="active-model-detail-legacy"),
    path("models/predict/", ActiveModelPredictView.as_view(), name="active-model-predict-legacy"),
]