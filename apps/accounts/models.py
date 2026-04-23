import uuid
import zoneinfo

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

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


class ActiveUserManager(CustomUserManager):
    """Manager that returns only non-deleted users by default"""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


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
    
    # Soft delete fields
    is_deleted = models.BooleanField(default=False, help_text="Whether this user has been soft-deleted")
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="When the user was soft-deleted")
    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_users',
        help_text="Administrator who deleted this user"
    )
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    preferred_timezone = models.CharField(
        max_length=60,
        choices=TIMEZONE_CHOICES,
        default="Africa/Nairobi",
        help_text="Your local timezone — meeting times will be displayed in this timezone.",
    )
    preferred_language = models.CharField(
        max_length=10,
        default="en",
        help_text="Your preferred language for the interface",
    )

    # Director profile fields
    bio = models.TextField(blank=True, help_text="Professional biography and background")
    education = models.TextField(blank=True, help_text="Educational qualifications")
    experience = models.TextField(blank=True, help_text="Professional experience")
    expertise = models.TextField(blank=True, help_text="Areas of expertise")
    linkedin_url = models.URLField(blank=True, help_text="LinkedIn profile URL")
    other_credentials = models.TextField(blank=True, help_text="Other professional credentials and certifications")
    board_tenure_start = models.DateField(null=True, blank=True, help_text="Date when board tenure started")
    board_position = models.CharField(max_length=100, blank=True, help_text="Specific position on the board")

    objects = CustomUserManager()
    active_objects = ActiveUserManager()

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

    @property
    def board_tenure_years(self):
        """Calculate years of board tenure"""
        if self.board_tenure_start:
            from django.utils import timezone
            years = (timezone.now().date() - self.board_tenure_start).days / 365.25
            return round(years, 1)
        return 0


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


class SSOProvider(models.Model):
    """Single Sign-On provider configuration"""

    PROVIDER_CHOICES = [
        ('okta', 'Okta'),
        ('azure_ad', 'Azure Active Directory'),
        ('google', 'Google Workspace'),
        ('auth0', 'Auth0'),
        ('keycloak', 'Keycloak'),
        ('ping', 'Ping Identity'),
        ('saml', 'Generic SAML'),
        ('oidc', 'Generic OIDC'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disabled', 'Disabled'),
        ('testing', 'Testing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Provider details
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disabled')
    
    # SAML Configuration
    saml_entity_id = models.CharField(max_length=255, blank=True, help_text="Entity ID for SAML")
    saml_sso_url = models.URLField(blank=True, help_text="SSO URL for SAML")
    saml_slo_url = models.URLField(blank=True, help_text="SLO URL for SAML")
    saml_certificate = models.TextField(blank=True, help_text="X.509 certificate")
    saml_metadata_url = models.URLField(blank=True, help_text="Metadata URL")
    
    # OIDC Configuration
    oidc_client_id = models.CharField(max_length=255, blank=True)
    oidc_client_secret = models.CharField(max_length=255, blank=True)
    oidc_issuer_url = models.URLField(blank=True)
    oidc_authorization_endpoint = models.URLField(blank=True)
    oidc_token_endpoint = models.URLField(blank=True)
    oidc_userinfo_endpoint = models.URLField(blank=True)
    oidc_jwks_uri = models.URLField(blank=True)
    
    # Mapping configuration
    email_attribute = models.CharField(max_length=100, default='email', help_text="Attribute name for email")
    first_name_attribute = models.CharField(max_length=100, default='given_name', help_text="Attribute name for first name")
    last_name_attribute = models.CharField(max_length=100, default='family_name', help_text="Attribute name for last name")
    role_attribute = models.CharField(max_length=100, blank=True, help_text="Attribute name for role")
    
    # Role mapping (JSON: {"admin": ["board_member", "it_administrator"], ...})
    role_mapping = models.JSONField(null=True, blank=True, help_text="Map SSO roles to system roles")
    
    # Auto-provisioning
    auto_provision_users = models.BooleanField(default=True, help_text="Automatically create users on first login")
    default_role = models.CharField(max_length=50, blank=True, help_text="Default role for auto-provisioned users")
    
    # Security
    require_encryption = models.BooleanField(default=True)
    allowed_domains = models.TextField(blank=True, help_text="Comma-separated list of allowed email domains")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_sso_providers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'SSO Provider'
        verbose_name_plural = 'SSO Providers'
        ordering = ['name']
        indexes = [
            models.Index(fields=['provider_type', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class UserSSOIdentity(models.Model):
    """Link between user and SSO identity"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sso_identities')
    provider = models.ForeignKey(SSOProvider, on_delete=models.CASCADE, related_name='user_identities')
    
    # SSO identity
    external_id = models.CharField(max_length=255, help_text="External user ID from SSO provider")
    external_username = models.CharField(max_length=255, blank=True)
    external_email = models.EmailField(blank=True)
    
    # SSO attributes
    attributes = models.JSONField(null=True, blank=True, help_text="Additional attributes from SSO")
    
    # Metadata
    first_login = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User SSO Identity'
        verbose_name_plural = 'User SSO Identities'
        ordering = ['-last_login_at']
        unique_together = [['provider', 'external_id']]
        indexes = [
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['provider', 'external_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.provider.name}"


class UserSession(models.Model):
    """Track user sessions for concurrent login limits"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('logout', 'Logged Out'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    
    # Session details
    session_key = models.CharField(max_length=255, unique=True, help_text="Django session key")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True, help_text="e.g., desktop, mobile, tablet")
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    
    # Location (optional, from IP geolocation)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Timestamps
    login_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_at = models.DateTimeField(null=True, blank=True)
    
    # Security
    is_suspicious = models.BooleanField(default=False, help_text="Flagged as potentially suspicious")
    risk_score = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    class Meta:
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', '-last_activity']),
            models.Index(fields=['status', '-last_activity']),
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.login_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_active(self):
        """Check if session is currently active"""
        if self.status != 'active':
            return False
        # Check if session has expired (3 minutes of inactivity for security)
        if timezone.now() - self.last_activity > timezone.timedelta(minutes=3):
            return False
        return True
    
    def terminate(self):
        """Terminate the session"""
        self.status = 'terminated'
        self.logout_at = timezone.now()
        self.save(update_fields=['status', 'logout_at'])


class EncryptionKey(models.Model):
    """Manage encryption keys for data encryption at rest"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('rotating', 'Rotating'),
        ('deprecated', 'Deprecated'),
        ('revoked', 'Revoked'),
    ]

    KEY_TYPE_CHOICES = [
        ('aes256', 'AES-256-GCM'),
        ('rsa4096', 'RSA-4096'),
        ('chacha20', 'ChaCha20-Poly1305'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Key details
    name = models.CharField(max_length=100, help_text="Friendly name for the key")
    key_type = models.CharField(max_length=20, choices=KEY_TYPE_CHOICES, default='aes256')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Key storage (encrypted at rest in database)
    encrypted_key = models.TextField(help_text="Encrypted key material")
    key_fingerprint = models.CharField(max_length=64, unique=True, help_text="SHA-256 fingerprint of the key")
    
    # Rotation
    rotation_interval_days = models.PositiveIntegerField(default=90, help_text="Days between key rotations")
    last_rotated_at = models.DateTimeField(auto_now_add=True)
    next_rotation_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_encryption_keys')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Encryption Key'
        verbose_name_plural = 'Encryption Keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['key_type']),
            models.Index(fields=['next_rotation_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_key_type_display()})"
    
    @property
    def needs_rotation(self):
        """Check if key needs rotation"""
        if self.status != 'active':
            return False
        if self.next_rotation_at and timezone.now() >= self.next_rotation_at:
            return True
        return False


class Language(models.Model):
    """Supported languages for the platform"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('beta', 'Beta'),
        ('disabled', 'Disabled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Language details
    code = models.CharField(max_length=10, unique=True, help_text="ISO 639-1 language code (e.g., en, fr, sw)")
    name = models.CharField(max_length=100, help_text="Language name in English")
    native_name = models.CharField(max_length=100, help_text="Language name in the language itself")
    
    # Locale
    locale_code = models.CharField(max_length=20, help_text="Locale code (e.g., en_US, fr_FR, sw_KE)")
    
    # Direction
    direction = models.CharField(max_length=3, choices=[('ltr', 'LTR'), ('rtl', 'RTL')], default='ltr')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Translation coverage
    translation_coverage = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Percentage of strings translated")
    
    # Flag emoji (optional)
    flag_emoji = models.CharField(max_length=10, blank=True, help_text="Flag emoji (e.g., 🇺🇸, 🇫🇷, 🇰🇪)")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Language'
        verbose_name_plural = 'Languages'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.native_name} ({self.code})"


class Translation(models.Model):
    """Translation strings for multi-language support"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Key for the translation
    key = models.CharField(max_length=500, help_text="Translation key (e.g., common.button.submit)")
    
    # Context
    context = models.CharField(max_length=200, blank=True, help_text="Context for the translation")
    module = models.CharField(max_length=100, blank=True, help_text="Module/app this belongs to")
    
    # Translations (JSON: {"en": "Submit", "fr": "Soumettre", "sw": "Wasilisha"})
    translations = models.JSONField(default=dict, help_text="Language code to translation mapping")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Translation'
        verbose_name_plural = 'Translations'
        ordering = ['key']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['module']),
        ]
    
    def __str__(self):
        return f"{self.key}"
    
    def get_translation(self, language_code, default=None):
        """Get translation for a specific language"""
        return self.translations.get(language_code, default or self.key)


class Committee(models.Model):
    """Board committees for organizing governance activities"""

    MEETING_TYPE_CHOICES = [
        ('board', 'Board Meeting'),
        ('audit', 'Audit Committee'),
        ('risk', 'Risk Committee'),
        ('governance', 'Governance Committee'),
        ('executive', 'Executive Committee'),
        ('nominating', 'Nominating Committee'),
        ('remuneration', 'Remuneration Committee'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Committee name")
    description = models.TextField(blank=True, help_text="Committee purpose and responsibilities")
    meeting_type = models.CharField(max_length=50, choices=MEETING_TYPE_CHOICES, default='board')
    
    # Organization context
    branch = models.ForeignKey(
        'agencies.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts_committees',
        help_text="Branch this committee belongs to"
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this committee is currently active")
    
    # Chairperson
    chairperson = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accounts_chaired_committees',
        help_text="Committee chairperson"
    )
    
    # Meeting schedule
    meeting_frequency = models.CharField(
        max_length=100,
        blank=True,
        help_text="How often this committee meets (e.g., 'Monthly', 'Quarterly')"
    )
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='accounts_created_committees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Committee'
        verbose_name_plural = 'Committees'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['meeting_type']),
            models.Index(fields=['branch']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_meeting_type_display()})"
    
    @property
    def active_members_count(self):
        """Count of active committee members"""
        return self.memberships.filter(
            is_active=True,
            left_at__isnull=True
        ).count()


class CommitteeMembership(models.Model):
    """Membership of users in committees"""

    ROLE_CHOICES = [
        ('chair', 'Chairperson'),
        ('vice_chair', 'Vice Chairperson'),
        ('secretary', 'Secretary'),
        ('member', 'Member'),
        ('observer', 'Observer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts_committee_memberships')
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='accounts_memberships')
    
    # Role and status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    is_active = models.BooleanField(default=True, help_text="Whether this membership is currently active")
    
    # Membership period
    joined_at = models.DateTimeField(auto_now_add=True, help_text="When user joined the committee")
    left_at = models.DateTimeField(null=True, blank=True, help_text="When user left the committee (if applicable)")
    
    # Appointment details
    appointed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointed_committee_memberships',
        help_text="Who appointed this member"
    )
    appointment_date = models.DateField(null=True, blank=True, help_text="Date of official appointment")
    
    # Voting rights
    has_voting_rights = models.BooleanField(default=True, help_text="Whether this member can vote")
    
    # Notes
    notes = models.TextField(blank=True, help_text="Additional notes about this membership")
    
    class Meta:
        verbose_name = 'Committee Membership'
        verbose_name_plural = 'Committee Memberships'
        ordering = ['committee', 'role', 'user']
        unique_together = ['user', 'committee']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['committee', 'is_active']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active and not self.left_at else "Inactive"
        return f"{self.user.get_full_name()} - {self.committee.name} ({self.get_role_display()}) - {status}"
    
    @property
    def is_currently_active(self):
        """Check if membership is currently active"""
        return self.is_active and (self.left_at is None or self.left_at > timezone.now())
    
    def terminate(self, terminated_by=None):
        """Terminate this committee membership"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save(update_fields=['is_active', 'left_at'])


class UserArchive(models.Model):
    """Archived user accounts for terminated users"""

    TERMINATION_REASON_CHOICES = [
        ('resignation', 'Resignation'),
        ('termination', 'Termination'),
        ('retirement', 'Retirement'),
        ('death', 'Death'),
        ('contract_end', 'Contract Ended'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User identification (preserved for records)
    original_user_id = models.UUIDField(help_text="Original user ID before archiving")
    email = models.EmailField(help_text="User's email address")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=50, help_text="User's role at time of termination")
    
    # Termination details
    termination_reason = models.CharField(max_length=50, choices=TERMINATION_REASON_CHOICES)
    termination_notes = models.TextField(blank=True, help_text="Additional notes about termination")
    
    # Who terminated
    terminated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='terminated_users',
        help_text="Administrator who terminated this account"
    )
    
    # Timestamps
    terminated_at = models.DateTimeField(auto_now_add=True, help_text="When the account was terminated")
    
    # Archived data (JSON snapshot of user data)
    archived_data = models.JSONField(default=dict, help_text="Snapshot of user data at termination time")
    
    # Retention
    retention_period_years = models.PositiveIntegerField(default=7, help_text="Years to retain this archive")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this archive can be permanently deleted")
    
    class Meta:
        verbose_name = 'User Archive'
        verbose_name_plural = 'User Archives'
        ordering = ['-terminated_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['terminated_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Archived: {self.email} - Terminated {self.terminated_at.strftime('%Y-%m-%d')}"
    
    def save(self, *args, **kwargs):
        """Calculate expiry date on save"""
        if not self.expires_at and self.retention_period_years:
            from datetime import timedelta
            self.expires_at = self.terminated_at + timedelta(days=self.retention_period_years * 365)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if archive retention period has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class FieldEditPermission(models.Model):
    """Define field-level editing restrictions for models"""

    FREEZE_CONDITION_CHOICES = [
        ('status', 'Freeze on Status'),
        ('date', 'Freeze After Date'),
        ('never', 'Never Freeze'),
        ('always', 'Always Read-Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Model and field identification
    model_name = models.CharField(max_length=100, help_text="Django model name (e.g., 'User', 'Meeting')")
    field_name = models.CharField(max_length=100, help_text="Field name to restrict")
    
    # Role-based permissions
    allowed_roles = models.JSONField(
        default=list,
        help_text="List of roles that can edit this field (e.g., ['it_administrator', 'company_secretary'])"
    )
    
    # Freeze conditions
    freeze_condition = models.CharField(
        max_length=20,
        choices=FREEZE_CONDITION_CHOICES,
        default='never',
        help_text="When to freeze this field from editing"
    )
    freeze_on_status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status value that triggers freeze (e.g., 'approved', 'published')"
    )
    freeze_after_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date after which field becomes read-only"
    )
    
    # Additional conditions
    freeze_after_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days after creation/edit after which field freezes"
    )
    require_approval = models.BooleanField(
        default=False,
        help_text="Whether editing this field requires approval"
    )
    
    # Description and metadata
    description = models.TextField(blank=True, help_text="Description of this restriction")
    is_active = models.BooleanField(default=True)
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_field_permissions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Field Edit Permission'
        verbose_name_plural = 'Field Edit Permissions'
        ordering = ['model_name', 'field_name']
        unique_together = ['model_name', 'field_name']
        indexes = [
            models.Index(fields=['model_name']),
            models.Index(fields=['freeze_condition']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.model_name}.{self.field_name} ({self.get_freeze_condition_display()})"
    
    def is_frozen(self, instance):
        """
        Check if field is frozen for a given instance.
        
        Args:
            instance: The model instance to check
            
        Returns:
            bool: True if field is frozen
        """
        if not self.is_active:
            return False
        
        if self.freeze_condition == 'always':
            return True
        
        if self.freeze_condition == 'never':
            return False
        
        if self.freeze_condition == 'status':
            if self.freeze_on_status and hasattr(instance, 'status'):
                return instance.status == self.freeze_on_status
        
        if self.freeze_condition == 'date':
            if self.freeze_after_date:
                return timezone.now() > self.freeze_after_date
            if self.freeze_after_days and hasattr(instance, 'created_at'):
                freeze_date = instance.created_at + timezone.timedelta(days=self.freeze_after_days)
                return timezone.now() > freeze_date
        
        return False
    
    def can_edit(self, user):
        """
        Check if user can edit this field based on role.
        
        Args:
            user: User instance
            
        Returns:
            bool: True if user can edit
        """
        if not self.is_active:
            return True
        
        if not self.allowed_roles:
            return True
        
        return user.role in self.allowed_roles


class Bookmark(models.Model):
    """User bookmarks for quick access to important items"""

    BOOKMARK_TYPES = [
        ('meeting', 'Meeting'),
        ('document', 'Document'),
        ('motion', 'Motion'),
        ('policy', 'Policy'),
        ('risk', 'Risk Assessment'),
        ('committee', 'Committee'),
        ('annual_meeting', 'Annual Meeting'),
        ('report', 'Report'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    
    # Target of bookmark
    bookmark_type = models.CharField(max_length=50, choices=BOOKMARK_TYPES)
    target_id = models.UUIDField(help_text="ID of the bookmarked item")
    target_url = models.CharField(max_length=500, help_text="URL to access the bookmarked item")
    
    # Display information
    title = models.CharField(max_length=255, help_text="Display title for the bookmark")
    description = models.TextField(blank=True, help_text="Optional description or notes")
    
    # Organization
    folder = models.CharField(
        max_length=100,
        blank=True,
        help_text="Folder/category for organizing bookmarks"
    )
    
    # Metadata
    is_pinned = models.BooleanField(default=False, help_text="Pin to top of bookmarks list")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Bookmark'
        verbose_name_plural = 'Bookmarks'
        ordering = ['-is_pinned', '-created_at']
        unique_together = ['user', 'bookmark_type', 'target_id']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['bookmark_type']),
            models.Index(fields=['folder']),
            models.Index(fields=['is_pinned']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"
