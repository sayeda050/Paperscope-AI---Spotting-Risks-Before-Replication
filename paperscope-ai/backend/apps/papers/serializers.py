from __future__ import annotations

from rest_framework import serializers

from .models import Paper, PaperText, PaperKeyword
from .validators import extract_arxiv_id, validate_uploaded_pdf


class SubmitPDFSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    file = serializers.FileField(write_only=True)

    def validate_file(self, value):
        return validate_uploaded_pdf(value)


class SubmitArxivSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    arxiv_link = serializers.CharField(max_length=1000)

    def validate_arxiv_link(self, value):
        return extract_arxiv_id(value)


class PaperKeywordSerializer(serializers.ModelSerializer):
    keyword = serializers.CharField(source='keyword.keyword_text', read_only=True)

    class Meta:
        model = PaperKeyword
        fields = ['keyword', 'weight']


class PaperTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperText
        fields = ['raw_text', 'cleaned_text']


class PaperListSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    latest_job_id = serializers.SerializerMethodField()
    latest_status = serializers.SerializerMethodField()
    latest_result_id = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = [
            'paper_id',
            'title',
            'source_type',
            'arxiv_id',
            'pdf_file_path',
            'uploaded_at',
            'user_name',
            'latest_job_id',
            'latest_status',
            'latest_result_id',
        ]

    def get_user_name(self, obj):
        first = getattr(obj.user, 'first_name', '') or ''
        last = getattr(obj.user, 'last_name', '') or ''
        return f'{first} {last}'.strip() or obj.user.email

    def _latest_job(self, obj):
        jobs = getattr(obj, 'analysis_jobs', None)
        if jobs is not None and hasattr(jobs, 'all'):
            return jobs.all().order_by('-created_at').first()
        return obj.analysis_jobs.order_by('-created_at').first()

    def get_latest_job_id(self, obj):
        job = self._latest_job(obj)
        return job.job_id if job else None

    def get_latest_status(self, obj):
        job = self._latest_job(obj)
        return job.status if job else None

    def get_latest_result_id(self, obj):
        job = self._latest_job(obj)
        if job and hasattr(job, 'result'):
            return job.result.result_id
        return None


class PaperDetailSerializer(serializers.ModelSerializer):
    text = PaperTextSerializer(read_only=True)
    keywords = PaperKeywordSerializer(source='paper_keywords', many=True, read_only=True)

    class Meta:
        model = Paper
        fields = [
            'paper_id',
            'title',
            'source_type',
            'arxiv_id',
            'pdf_file_path',
            'uploaded_at',
            'text',
            'keywords',
        ]
