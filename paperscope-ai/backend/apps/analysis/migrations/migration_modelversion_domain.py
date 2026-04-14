"""
Migration: add domain and run_id fields to ModelVersion.

Generated for:  apps/analysis/models.py
Depends on:     the latest existing migration in apps/analysis/migrations/

USAGE:
  Place this file in:  backend/apps/analysis/migrations/
  Rename it to follow your existing migration numbering, e.g.:
    0005_modelversion_domain_runid.py
  (Replace 0005 with the next number after your last migration)

  Then run:
    python manage.py migrate analysis
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    # ── UPDATE THIS to your actual last migration name ────────────────────
    dependencies = [
        ("analysis", "0001_initial"),   # ← replace with your real last migration
    ]

    operations = [
        migrations.AddField(
            model_name="modelversion",
            name="domain",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=64,
                help_text="Training domain tag, e.g. 'ml', 'all', 'physics'.",
            ),
        ),
        migrations.AddField(
            model_name="modelversion",
            name="run_id",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=64,
                help_text="Pipeline run timestamp, e.g. '20260414_191800'.",
            ),
        ),
    ]
