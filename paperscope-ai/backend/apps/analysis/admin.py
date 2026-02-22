from django.contrib import admin
from .models import AnalysisJob, AnalysisResult, ModelVersion

admin.site.register(AnalysisJob)
admin.site.register(AnalysisResult)
admin.site.register(ModelVersion)