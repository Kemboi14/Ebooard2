import uuid
import zoneinfo

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

# Common timezones for the regions Enwealth operates in
TIMEZONE_CHOICES = sorted(
    [
        ("Africa/Nairobi", "Kenya / Uganda / Tanzania (EAT, UTC+3)"),
        ("Africa/Kampala", "Uganda (EAT, UTC+3)"),
        ("Indian/Mauritius", "Mauritius (MUT, UTC+4)"),
        ("Africa/Johannesburg", "South Africa (SAST, UTC+2)"),
        ("Africa/Lagos", "Nigeria (WAT, UTC+1)"),
        ("Africa/Accra", "Ghana (GMT, UTC+0)"),
        ("Africa/Cairo", "Egypt (EET, UTC+2)"),
        ("Europe/London", "United Kingdom (GMT/BST)"),
        ("Europe/Paris", "France / CET (UTC+1)"),
        ("Asia/Dubai", "UAE (GST, UTC+4)"),
        ("Asia/Kolkata", "India (IST, UTC+5:30)"),
        ("UTC", "UTC"),
    ],
    key=lambda x: x[1],
)


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ("board_member", "Board Member"),
        ("company_secretary", "Company Secretary"),
        ("executive_management", "Executive Management"),
        ("compliance_officer", "Compliance Officer"),
        ("it_administrator", "IT Administrator"),
        ("internal_audit", "Internal Audit"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to="profiles/", null=True, blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    preferred_timezone = models.CharField(
        max_length=60,
        choices=TIMEZONE_CHOICES,
        default="Africa/Nairobi",
        help_text="Your local timezone — meeting times will be displayed in this timezone.",
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "auth_user"

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_timezone(self):
        """Return a zoneinfo.ZoneInfo object for this user's preferred timezone."""
        try:
            return zoneinfo.ZoneInfo(self.preferred_timezone)
        except (zoneinfo.ZoneInfoNotFoundError, Exception):
            return zoneinfo.ZoneInfo("Africa/Nairobi")

    def localise_dt(self, dt):
        """Convert a UTC-aware datetime to this user's local timezone."""
        from django.utils import timezone as dj_tz

        if dt is None:
            return None
        if dj_tz.is_naive(dt):
            dt = dj_tz.make_aware(dt, zoneinfo.ZoneInfo("UTC"))
        return dt.astimezone(self.get_timezone())


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_history"
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.created_at}"
