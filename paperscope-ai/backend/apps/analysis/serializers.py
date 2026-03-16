from __future__ import annotations

from rest_framework import serializers

from .models import AnalysisJob, AnalysisResult, ModelVersion


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = [
            'model_version_id',
            'model_name',
            'artifact_path_vectorizer',
            'artifact_path_classifier',
            'created_at',
            'active_flag',
        ]


class AnalysisResultSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model_version.model_name', read_only=True)

    class Meta:
        model = AnalysisResult
        fields = [
            'result_id',
            'job_id',
            'model_version_id',
            'model_name',
            'risk_score',
            'risk_label',
            'explanation_json',
            'completed_at',
        ]


class AnalysisJobListSerializer(serializers.ModelSerializer):
    paper_title = serializers.CharField(source='paper.title', read_only=True)
    result = AnalysisResultSerializer(read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisJob
        fields = [
            'job_id',
            'paper_id',
            'paper_title',
            'user_id',
            'user_name',
            'status',
            'created_at',
            'completed_at',
            'error_message',
            'result',
        ]

    def get_user_name(self, obj):
        if not getattr(obj, 'user', None):
            return ''
        first = getattr(obj.user, 'first_name', '') or ''
        last = getattr(obj.user, 'last_name', '') or ''
        return f'{first} {last}'.strip() or obj.user.email


class AnalysisJobDetailSerializer(AnalysisJobListSerializer):
    pass
