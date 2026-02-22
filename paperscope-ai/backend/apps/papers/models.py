from django.db import models
from apps.users.models import User


class Paper(models.Model):
    class SourceType(models.TextChoices):
        UPLOAD_PDF = "UPLOAD_PDF", "UPLOAD_PDF"
        ARXIV_LINK = "ARXIV_LINK", "ARXIV_LINK"

    paper_id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="papers",
        db_column="user_id",
    )

    title = models.CharField(max_length=1000)
    source_type = models.CharField(max_length=50, choices=SourceType.choices)

    arxiv_id = models.CharField(max_length=100, blank=True, null=True)
    pdf_file_path = models.CharField(max_length=2048, blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paper"
        indexes = [
            models.Index(fields=["user"], name="idx_paper_user_id"),
        ]

    def __str__(self):
        return f"{self.paper_id} - {self.title}"


class PaperText(models.Model):
    paper_text_id = models.BigAutoField(primary_key=True)

    # 1-to-1 enforced by UNIQUE on paper_id in schema
    paper = models.OneToOneField(
        Paper,
        on_delete=models.CASCADE,
        related_name="text",
        db_column="paper_id",
    )

    raw_text = models.TextField()
    cleaned_text = models.TextField()

    class Meta:
        db_table = "paper_text"

    def __str__(self):
        return f"PaperText({self.paper_id})"


class Keyword(models.Model):
    keyword_id = models.BigAutoField(primary_key=True)
    keyword_text = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "keyword"

    def __str__(self):
        return self.keyword_text


class PaperKeyword(models.Model):
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        db_column="paper_id",
        related_name="paper_keywords",
    )
    keyword = models.ForeignKey(
        Keyword,
        on_delete=models.CASCADE,
        db_column="keyword_id",
        related_name="keyword_papers",
    )

    weight = models.DecimalField(max_digits=10, decimal_places=6)

    class Meta:
        db_table = "paper_keyword"
        constraints = [
            models.UniqueConstraint(fields=["paper", "keyword"], name="pk_paper_keyword")
        ]
        indexes = [
            models.Index(fields=["keyword"], name="idx_paper_keyword_keyword"),
        ]

    def __str__(self):
        return f"{self.paper_id}-{self.keyword_id}"