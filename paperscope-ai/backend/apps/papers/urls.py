from django.urls import path

from .views import (
    SubmitPDFView,
    SubmitArxivView,
    MyPaperListView,
    AdminPaperListView,
    PaperDetailView,
    PaperTextView,
)

urlpatterns = [
    path('submit-pdf/', SubmitPDFView.as_view(), name='submit-pdf'),
    path('submit-arxiv/', SubmitArxivView.as_view(), name='submit-arxiv'),
    path('mine/', MyPaperListView.as_view(), name='my-papers'),
    path('admin/', AdminPaperListView.as_view(), name='admin-papers'),
    path('<int:paper_id>/', PaperDetailView.as_view(), name='paper-detail'),
    path('<int:paper_id>/text/', PaperTextView.as_view(), name='paper-text'),
]
