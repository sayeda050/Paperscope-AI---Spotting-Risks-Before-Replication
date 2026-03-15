from __future__ import annotations

from collections import Counter

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.logs_app.models import ErrorLog
from apps.papers.models import Paper

from .models import AnalysisJob, AnalysisResult
from .serializers import AnalysisJobDetailSerializer, AnalysisJobListSerializer, AnalysisResultSerializer
from .services import is_admin_user, retry_analysis_job, sync_model_versions_from_registry


User = get_user_model()


class UserDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = AnalysisJob.objects.filter(user=request.user).select_related('paper').prefetch_related('result')
        papers_count = Paper.objects.filter(user=request.user).count()
        completed = jobs.filter(status=AnalysisJob.Status.DONE).count()
        in_progress = jobs.filter(status__in=[AnalysisJob.Status.QUEUED, AnalysisJob.Status.PROCESSING]).count()
        failed = jobs.filter(status=AnalysisJob.Status.FAILED).count()
        recent_jobs = jobs.order_by('-created_at')[:5]

        return Response(
            {
                'stats': {
                    'total_papers': papers_count,
                    'completed_jobs': completed,
                    'in_progress_jobs': in_progress,
                    'failed_jobs': failed,
                },
                'recent_jobs': AnalysisJobListSerializer(recent_jobs, many=True).data,
            }
        )


class UserJobListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AnalysisJob.objects.filter(user=request.user).select_related('paper', 'user').prefetch_related('result').order_by('-created_at')
        return Response({'jobs': AnalysisJobListSerializer(qs, many=True).data})


class UserHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AnalysisJob.objects.filter(user=request.user).select_related('paper', 'user').prefetch_related('result').order_by('-created_at')
        return Response({'history': AnalysisJobListSerializer(qs, many=True).data})


class UserJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            job = AnalysisJob.objects.select_related('paper', 'user').prefetch_related('result').get(job_id=job_id, user=request.user)
        except AnalysisJob.DoesNotExist:
            return Response({'detail': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'job': AnalysisJobDetailSerializer(job).data})


class UserResultByJobView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        try:
            result = AnalysisResult.objects.select_related('job__paper', 'model_version').get(job_id=job_id, job__user=request.user)
        except AnalysisResult.DoesNotExist:
            return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'result': AnalysisResultSerializer(result).data, 'paper_title': result.job.paper.title})


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        sync_model_versions_from_registry()
        users_count = User.objects.count()
        papers_count = Paper.objects.count()
        jobs = AnalysisJob.objects.select_related('paper').prefetch_related('result')
        logs_count = ErrorLog.objects.count()
        completed = jobs.filter(status=AnalysisJob.Status.DONE).count()
        failed = jobs.filter(status=AnalysisJob.Status.FAILED).count()
        active_model = next((m for m in sync_model_versions_from_registry() if m.active_flag), None)

        jobs_by_day_qs = jobs.extra(select={'day': "DATE(created_at)"}).values('day').annotate(count=Count('job_id')).order_by('day')
        jobs_by_day = [{'day': str(row['day']), 'count': row['count']} for row in jobs_by_day_qs]

        risk_counter = Counter(
            AnalysisResult.objects.values_list('risk_label', flat=True)
        )
        risk_dist = [
            {'name': 'Low', 'value': risk_counter.get('Low', 0)},
            {'name': 'Medium', 'value': risk_counter.get('Med', 0)},
            {'name': 'High', 'value': risk_counter.get('High', 0)},
        ]
        status_dist = [
            {'name': 'Done', 'value': completed},
            {'name': 'Processing', 'value': jobs.filter(status=AnalysisJob.Status.PROCESSING).count()},
            {'name': 'Queued', 'value': jobs.filter(status=AnalysisJob.Status.QUEUED).count()},
            {'name': 'Failed', 'value': failed},
        ]

        return Response(
            {
                'stats': {
                    'total_users': users_count,
                    'total_papers': papers_count,
                    'total_jobs': jobs.count(),
                    'completed_jobs': completed,
                    'failed_jobs': failed,
                    'error_logs': logs_count,
                    'active_model': active_model.model_name if active_model else '',
                },
                'jobs_by_day': jobs_by_day,
                'risk_distribution': risk_dist,
                'status_distribution': status_dist,
            }
        )


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.annotate(total_papers=Count('papers')).order_by('-created_at')
        payload = []
        for user in users:
            payload.append(
                {
                    'user_id': user.user_id,
                    'name': f'{user.first_name} {user.last_name}'.strip(),
                    'email': user.email,
                    'role': 'Admin' if getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'ADMIN' else 'User',
                    'joined': user.created_at,
                    'total_papers': user.total_papers,
                }
            )
        return Response({'users': payload})


class AdminJobListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = AnalysisJob.objects.select_related('paper', 'user').prefetch_related('result').order_by('-created_at')
        return Response({'jobs': AnalysisJobListSerializer(qs, many=True).data})


class AdminRetryJobView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            job = AnalysisJob.objects.select_related('paper__text', 'user').get(job_id=job_id)
        except AnalysisJob.DoesNotExist:
            return Response({'detail': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        retried_job = retry_analysis_job(job, requested_by=request.user)
        return Response({'job': AnalysisJobDetailSerializer(retried_job).data})


class AdminResultListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        qs = AnalysisResult.objects.select_related('job__paper', 'model_version').order_by('-completed_at')
        results = []
        for result in qs:
            results.append(
                {
                    'result_id': result.result_id,
                    'job_id': result.job_id,
                    'paper_title': result.job.paper.title,
                    'risk_score': float(result.risk_score),
                    'risk_label': result.risk_label,
                    'completed_at': result.completed_at,
                }
            )
        return Response({'results': results})


class AdminResultDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, result_id):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            result = AnalysisResult.objects.select_related('job__paper', 'model_version').get(result_id=result_id)
        except AnalysisResult.DoesNotExist:
            return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                'result': AnalysisResultSerializer(result).data,
                'paper_title': result.job.paper.title,
                'job_id': result.job_id,
            }
        )


class AdminErrorLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        logs = ErrorLog.objects.select_related('user', 'paper').order_by('-timestamp')
        payload = []
        for log in logs:
            payload.append(
                {
                    'error_id': log.error_id,
                    'module_name': log.module_name,
                    'message': log.message,
                    'timestamp': log.timestamp,
                    'user': (f'{log.user.first_name} {log.user.last_name}'.strip() if log.user else ''),
                    'paper': (log.paper.title if log.paper else ''),
                }
            )
        return Response({'logs': payload})
