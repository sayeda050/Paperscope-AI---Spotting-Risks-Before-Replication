from django.db import models
from apps.users.models import User
from apps.papers.models import Paper


class ErrorLog(models.Model):
    error_id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        db_column="user_id",
        related_name="error_logs",
    )

    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        db_column="paper_id",
        related_name="error_logs",
    )

    module_name = models.CharField(max_length=255)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_column="timestamp")

    class Meta:
        db_table = "error_log"
        indexes = [
            models.Index(fields=["user"], name="idx_error_log_user"),
            models.Index(fields=["paper"], name="idx_error_log_paper"),
            models.Index(fields=["timestamp"], name="idx_error_log_timestamp"),
        ]

    def __str__(self):
        return f"Error({self.error_id}) {self.module_name}"