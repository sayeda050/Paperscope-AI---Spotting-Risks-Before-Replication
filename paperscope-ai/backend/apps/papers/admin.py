from django.contrib import admin
from .models import Paper, PaperText, Keyword, PaperKeyword

admin.site.register(Paper)
admin.site.register(PaperText)
admin.site.register(Keyword)
admin.site.register(PaperKeyword)