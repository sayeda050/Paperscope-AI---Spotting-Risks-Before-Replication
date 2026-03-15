from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.serializers import AnalysisJobDetailSerializer
from apps.analysis.services import is_admin_user, run_analysis_for_paper
from apps.logs_app.utils import log_error

from .models import Paper
from .serializers import (
    PaperDetailSerializer,
    PaperListSerializer,
    SubmitArxivSerializer,
    SubmitPDFSerializer,
)
from .services.arxiv_client import ArxivClient, ArxivClientError
from .services.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf_bytes,
    extract_title_from_pdf_bytes,
)


class SubmitPDFView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = SubmitPDFSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        provided_title = (serializer.validated_data.get("title") or "").strip()

        relative_path = default_storage.save(
            f"papers/{uuid.uuid4().hex}_{uploaded_file.name}",
            uploaded_file,
        )
        absolute_path = Path(settings.MEDIA_ROOT) / relative_path
        pdf_bytes = absolute_path.read_bytes()

        filename_stem = Path(uploaded_file.name).stem
        extracted_title = extract_title_from_pdf_bytes(pdf_bytes)

        # important:
        # if old frontend sends filename stem as "auto-filled title",
        # we still override it with the real PDF title
        if not provided_title:
            final_title = extracted_title or filename_stem
        elif provided_title == filename_stem and extracted_title:
            final_title = extracted_title
        else:
            final_title = provided_title

        paper = Paper.objects.create(
            user=request.user,
            title=final_title,
            source_type=Paper.SourceType.UPLOAD_PDF,
            pdf_file_path=str(relative_path),
        )

        try:
            raw_text, cleaned_text = extract_text_from_pdf_bytes(pdf_bytes)
            job = run_analysis_for_paper(
                paper=paper,
                user=request.user,
                title=final_title,
                cleaned_text=cleaned_text,
                raw_text=raw_text,
            )
            return Response(
                {
                    "paper": PaperDetailSerializer(paper).data,
                    "job": AnalysisJobDetailSerializer(job).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            log_error(
                module_name="papers.submit_pdf",
                message=str(exc),
                user=request.user,
                paper=paper,
            )
            return Response(
                {"detail": str(exc), "paper_id": paper.paper_id},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SubmitArxivView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubmitArxivSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        arxiv_id = serializer.validated_data["arxiv_link"]
        provided_title = (serializer.validated_data.get("title") or "").strip()

        try:
            paper_data = ArxivClient().fetch(arxiv_id)
            title = provided_title or paper_data.title

            relative_path = default_storage.save(
                f"papers/{uuid.uuid4().hex}_{arxiv_id}.pdf",
                ContentFile(paper_data.pdf_bytes),
            )

            paper = Paper.objects.create(
                user=request.user,
                title=title,
                source_type=Paper.SourceType.ARXIV_LINK,
                arxiv_id=arxiv_id,
                pdf_file_path=str(relative_path),
            )

            raw_text, cleaned_text = extract_text_from_pdf_bytes(paper_data.pdf_bytes)
            job = run_analysis_for_paper(
                paper=paper,
                user=request.user,
                title=title,
                cleaned_text=cleaned_text,
                raw_text=raw_text,
                abstract=paper_data.abstract,
            )
            return Response(
                {
                    "paper": PaperDetailSerializer(paper).data,
                    "job": AnalysisJobDetailSerializer(job).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except (ArxivClientError, PDFExtractionError, Exception) as exc:
            log_error(
                module_name="papers.submit_arxiv",
                message=str(exc),
                user=request.user,
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MyPaperListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Paper.objects.filter(user=request.user)
            .select_related("user")
            .prefetch_related("analysis_jobs__result")
            .order_by("-uploaded_at")
        )
        return Response({"papers": PaperListSerializer(qs, many=True).data})


class AdminPaperListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            Paper.objects.select_related("user")
            .prefetch_related("analysis_jobs__result")
            .order_by("-uploaded_at")
        )
        return Response({"papers": PaperListSerializer(qs, many=True).data})


class PaperDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, paper_id):
        qs = Paper.objects.select_related("user").prefetch_related(
            "paper_keywords__keyword",
            "analysis_jobs__result",
        )
        if is_admin_user(request.user):
            return qs.get(paper_id=paper_id)
        return qs.get(paper_id=paper_id, user=request.user)

    def get(self, request, paper_id):
        try:
            paper = self.get_object(request, paper_id)
        except Paper.DoesNotExist:
            return Response({"detail": "Paper not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"paper": PaperDetailSerializer(paper).data})


class PaperTextView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, paper_id):
        try:
            paper = Paper.objects.select_related("text").get(paper_id=paper_id)
            if paper.user_id != request.user.user_id and not is_admin_user(request.user):
                return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
        except Paper.DoesNotExist:
            return Response({"detail": "Paper not found."}, status=status.HTTP_404_NOT_FOUND)

        text_obj = getattr(paper, "text", None)
        if text_obj is None:
            return Response({"detail": "Extracted text not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "raw_text": text_obj.raw_text,
                "cleaned_text": text_obj.cleaned_text,
            }
        )