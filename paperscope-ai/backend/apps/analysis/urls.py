from django.urls import path

from .views import (
    UserDashboardView,
    UserJobListView,
    UserHistoryView,
    UserJobDetailView,
    UserResultByJobView,
    AdminDashboardView,
    AdminUserListView,
    AdminJobListView,
    AdminRetryJobView,
    AdminResultListView,
    AdminResultDetailView,
    AdminErrorLogListView,
)

urlpatterns = [
    path('dashboard/', UserDashboardView.as_view(), name='user-dashboard'),
    path('jobs/', UserJobListView.as_view(), name='user-jobs'),
    path('history/', UserHistoryView.as_view(), name='user-history'),
    path('jobs/<int:job_id>/', UserJobDetailView.as_view(), name='user-job-detail'),
    path('results/<int:job_id>/', UserResultByJobView.as_view(), name='user-result-by-job'),
    path('admin/dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/jobs/', AdminJobListView.as_view(), name='admin-jobs'),
    path('admin/jobs/<int:job_id>/retry/', AdminRetryJobView.as_view(), name='admin-job-retry'),
    path('admin/results/', AdminResultListView.as_view(), name='admin-results'),
    path('admin/results/<int:result_id>/', AdminResultDetailView.as_view(), name='admin-result-detail'),
    path('admin/error-logs/', AdminErrorLogListView.as_view(), name='admin-error-logs'),
]