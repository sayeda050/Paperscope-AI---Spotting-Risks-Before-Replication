from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)

        if password:
            user.set_password(password)
        else:
            # allow Google-only accounts (password_hash nullable in schema)
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("role") != User.Role.ADMIN:
            raise ValueError("Superuser must have role=ADMIN")
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email=email, username=username, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "ADMIN"
        GENERAL_USER = "GENERAL_USER", "GENERAL_USER"

    user_id = models.BigAutoField(primary_key=True)

    email = models.EmailField(max_length=320, unique=True)
    username = models.CharField(max_length=150, unique=True)

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    # match schema column name password_hash (nullable for Google-only accounts)
    password = models.CharField(max_length=1024, db_column="password_hash", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GENERAL_USER)

    # Django-required flags (your schema didn’t list them, but Django needs them)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.email


class AuthProvider(models.Model):
    class ProviderType(models.TextChoices):
        EMAIL = "EMAIL", "EMAIL"
        GOOGLE = "GOOGLE", "GOOGLE"

    provider_id = models.BigAutoField(primary_key=True)
    provider_type = models.CharField(max_length=100, choices=ProviderType.choices)
    provider_uid = models.CharField(max_length=512)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="auth_providers",
        db_column="user_id",
    )

    class Meta:
        db_table = "auth_provider"
        constraints = [
            models.UniqueConstraint(
                fields=["provider_type", "provider_uid"],
                name="uq_auth_provider_type_uid",
            )
        ]

    def __str__(self):
        return f"{self.provider_type}:{self.provider_uid}"