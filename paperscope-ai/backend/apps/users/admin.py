from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, AuthProvider


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("user_id",)
    list_display = ("user_id", "email", "username", "role", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "username")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "first_name", "last_name", "password1", "password2")}),
    )
    readonly_fields = ("created_at",)


admin.site.register(AuthProvider)