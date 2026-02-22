from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.users.models import User
from apps.papers.models import Paper


class AnalysisJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "QUEUED"
        PROCESSING = "PROCESSING", "PROCESSING"
        DONE = "DONE", "DONE"
        FAILED = "FAILED", "FAILED"

    job_id = models.BigAutoField(primary_key=True)

    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name="analysis_jobs",
        db_column="paper_id",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="analysis_jobs",
        db_column="user_id",
    )

    status = models.CharField(max_length=20, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "analysis_job"
        indexes = [
            models.Index(fields=["paper"], name="idx_analysis_job_paper_id"),
            models.Index(fields=["user"], name="idx_analysis_job_user_id"),
            models.Index(fields=["status"], name="idx_analysis_job_status"),
        ]

    def __str__(self):
        return f"Job({self.job_id}) {self.status}"


class ModelVersion(models.Model):
    model_version_id = models.BigAutoField(primary_key=True)
    model_name = models.CharField(max_length=255)

    artifact_path_vectorizer = models.CharField(max_length=2048)
    artifact_path_classifier = models.CharField(max_length=2048)

    created_at = models.DateTimeField(auto_now_add=True)
    active_flag = models.BooleanField(default=True)

    class Meta:
        db_table = "model_version"
        constraints = [
            # only one active model at a time (partial unique index)
            models.UniqueConstraint(
                fields=["active_flag"],
                condition=Q(active_flag=True),
                name="uq_model_version_one_active",
            )
        ]

    def __str__(self):
        return f"{self.model_name} (active={self.active_flag})"


class AnalysisResult(models.Model):
    result_id = models.BigAutoField(primary_key=True)

    # 1-to-1 with AnalysisJob (UNIQUE job_id)
    job = models.OneToOneField(
        AnalysisJob,
        on_delete=models.CASCADE,
        related_name="result",
        db_column="job_id",
    )

    model_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.CASCADE,
        related_name="results",
        db_column="model_version_id",
    )

    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    risk_label = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[("Low", "Low"), ("Med", "Med"), ("High", "High")],
    )

    explanation_json = models.JSONField()
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "analysis_result"
        indexes = [
            models.Index(fields=["model_version"], name="idx_analysis_result_model"),
        ]

    def __str__(self):
        return f"Result({self.result_id}) score={self.risk_score}"