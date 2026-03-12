import hashlib
import os
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User


def esig_upload_path(instance, filename):
    """Route uploads to a structured, non-guessable path."""
    ext = os.path.splitext(filename)[1].lower()
    return f"esignature/documents/{instance.pk}{ext}"


def signed_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"esignature/signed/{instance.pk}{ext}"


def signature_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"esignature/signatures/{instance.user.pk}/{uuid.uuid4()}{ext}"


# ---------------------------------------------------------------------------
# SignableDocument
# ---------------------------------------------------------------------------


class SignableDocument(models.Model):
    """
    A PDF document uploaded for electronic signing.

    The original file is stored at upload time and its SHA-256 hash is recorded.
    Once all required signers have signed, a final signed PDF is produced and
    stored separately.  The original is never overwritten.
    """

    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_FULLY_SIGNED = "fully_signed"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending – Awaiting First Signer"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_FULLY_SIGNED, "Fully Signed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    ACCESS_LEVEL_CHOICES = [
        ("private", "Private – Signers & Uploader Only"),
        ("board", "Board Members"),
        ("committee", "Committee Members"),
        ("restricted", "Restricted – Named Viewers Only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    reference_number = models.CharField(
        max_length=60,
        unique=True,
        blank=True,
        help_text="Auto-generated reference, e.g. ESIG-2025-00042",
    )
    version = models.PositiveIntegerField(default=1)

    # Files
    original_file = models.FileField(upload_to=esig_upload_path)
    signed_file = models.FileField(upload_to=signed_upload_path, null=True, blank=True)

    # Integrity
    original_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 of the original file at upload time",
    )
    signed_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 of the final signed file",
    )

    # Workflow
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    require_ordered_signing = models.BooleanField(
        default=True,
        help_text="Signers must sign in the specified order",
    )
    require_otp = models.BooleanField(
        default=True,
        help_text="Each signer must verify via OTP before signing",
    )
    access_level = models.CharField(
        max_length=20, choices=ACCESS_LEVEL_CHOICES, default="private"
    )

    # Expiry
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Document / signing deadline.  NULL = no expiry.",
    )

    # Ownership
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="uploaded_signable_documents",
    )

    # Branch / agency context (optional – links into multi-agency structure)
    branch = models.ForeignKey(
        "agencies.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signable_documents",
    )

    # Metadata
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0, help_text="Size in bytes")
    mime_type = models.CharField(max_length=100, default="application/pdf")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalised_at = models.DateTimeField(
        null=True, blank=True, help_text="When the last signature was collected"
    )

    class Meta:
        verbose_name = "Signable Document"
        verbose_name_plural = "Signable Documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["uploaded_by", "-created_at"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["reference_number"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.reference_number}] – {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse("esignature:document_detail", kwargs={"pk": self.pk})

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1_048_576:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / 1_048_576:.1f} MB"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def pending_signers(self):
        return self.signers.filter(
            status__in=[
                SignerAssignment.STATUS_PENDING,
                SignerAssignment.STATUS_NOTIFIED,
            ]
        ).order_by("signing_order")

    @property
    def completed_signers(self):
        return self.signers.filter(status=SignerAssignment.STATUS_SIGNED).order_by(
            "signed_at"
        )

    @property
    def total_signers(self):
        return self.signers.count()

    @property
    def signed_count(self):
        return self.signers.filter(status=SignerAssignment.STATUS_SIGNED).count()

    @property
    def completion_percentage(self):
        total = self.total_signers
        if total == 0:
            return 0
        return int((self.signed_count / total) * 100)

    @property
    def next_signer(self):
        """Return the next signer assignment in ordered workflows."""
        if not self.require_ordered_signing:
            return None
        return (
            self.signers.filter(
                status__in=[
                    SignerAssignment.STATUS_PENDING,
                    SignerAssignment.STATUS_NOTIFIED,
                ]
            )
            .order_by("signing_order")
            .first()
        )

    # ------------------------------------------------------------------
    # Integrity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hash(file_field):
        """Return the SHA-256 hex-digest of a Django FieldFile."""
        sha = hashlib.sha256()
        file_field.seek(0)
        for chunk in iter(lambda: file_field.read(65536), b""):
            sha.update(chunk)
        file_field.seek(0)
        return sha.hexdigest()

    def verify_original_integrity(self):
        """Return True if the stored hash matches the file on disk."""
        if not self.original_file or not self.original_hash:
            return False
        try:
            return self.compute_hash(self.original_file) == self.original_hash
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Reference number
    # ------------------------------------------------------------------

    def _generate_reference(self):
        year = timezone.now().year
        seq = SignableDocument.objects.filter(created_at__year=year).count() + 1
        return f"ESIG-{year}-{seq:05d}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            self.reference_number = self._generate_reference()
        if self.original_file and not self.original_hash:
            self.file_name = os.path.basename(self.original_file.name)
            self.file_size = self.original_file.size
            self.original_hash = self.compute_hash(self.original_file)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# SignerAssignment
# ---------------------------------------------------------------------------


class SignerAssignment(models.Model):
    """
    One row per (document, signer) pair.

    Tracks whether the signer has been notified, whether they have signed
    or rejected, their OTP verification status, and forensic metadata
    (IP, timestamp, device info).
    """

    STATUS_PENDING = "pending"
    STATUS_NOTIFIED = "notified"
    STATUS_VIEWED = "viewed"
    STATUS_OTP_VERIFIED = "otp_verified"
    STATUS_SIGNED = "signed"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_NOTIFIED, "Notified"),
        (STATUS_VIEWED, "Viewed"),
        (STATUS_OTP_VERIFIED, "OTP Verified"),
        (STATUS_SIGNED, "Signed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
    ]

    ROLE_SIGNER = "signer"
    ROLE_APPROVER = "approver"
    ROLE_WITNESS = "witness"
    ROLE_CC = "cc"

    ROLE_CHOICES = [
        (ROLE_SIGNER, "Signer"),
        (ROLE_APPROVER, "Approver"),
        (ROLE_WITNESS, "Witness"),
        (ROLE_CC, "CC / Viewer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        SignableDocument, on_delete=models.CASCADE, related_name="signers"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="signature_assignments",
        null=True,
        blank=True,
        help_text="Leave blank for external signers (use email below)",
    )

    # External signer support (no system account required)
    external_name = models.CharField(max_length=150, blank=True)
    external_email = models.EmailField(blank=True)

    # Workflow
    signing_order = models.PositiveIntegerField(
        default=1, help_text="Order in which this person signs (1 = first)"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_SIGNER)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    is_required = models.BooleanField(
        default=True,
        help_text="Document cannot be fully signed until this person signs",
    )

    # Secure signing link token
    signing_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # Signature placement hint stored as JSON, e.g.:
    # {"page": 1, "x": 100, "y": 200, "width": 200, "height": 60}
    placement = models.JSONField(
        null=True,
        blank=True,
        help_text="Where to embed the signature in the PDF",
    )

    # OTP tracking
    otp_verified = models.BooleanField(default=False)
    otp_verified_at = models.DateTimeField(null=True, blank=True)

    # Outcome
    signed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Forensic metadata
    signed_ip = models.GenericIPAddressField(null=True, blank=True)
    signed_user_agent = models.TextField(blank=True)
    signed_device_info = models.JSONField(
        null=True,
        blank=True,
        help_text="Browser, OS, screen size etc captured at signing time",
    )

    # Notification tracking
    notified_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Signer Assignment"
        verbose_name_plural = "Signer Assignments"
        ordering = ["document", "signing_order"]
        unique_together = [["document", "signing_order"]]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["document", "status"]),
            models.Index(fields=["signing_token"]),
        ]

    def __str__(self):
        name = self.display_name
        return f"{name} → {self.document.title} (#{self.signing_order})"

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.email
        return self.external_name or self.external_email or "Unknown Signer"

    @property
    def display_email(self):
        if self.user:
            return self.user.email
        return self.external_email

    @property
    def token_is_valid(self):
        if self.token_expires_at and timezone.now() > self.token_expires_at:
            return False
        return self.status not in (
            self.STATUS_SIGNED,
            self.STATUS_REJECTED,
            self.STATUS_EXPIRED,
        )

    def get_signing_url(self):
        return reverse("esignature:sign_document", kwargs={"token": self.signing_token})


# ---------------------------------------------------------------------------
# CapturedSignature
# ---------------------------------------------------------------------------


class CapturedSignature(models.Model):
    """
    The actual signature image drawn or uploaded by a signer.

    A user may have multiple saved signatures; one is marked as default.
    When a document is signed the used signature is recorded via the
    assignment's FK below.
    """

    SOURCE_DRAWN = "drawn"
    SOURCE_UPLOADED = "uploaded"
    SOURCE_TYPED = "typed"

    SOURCE_CHOICES = [
        (SOURCE_DRAWN, "Drawn on Signature Pad"),
        (SOURCE_UPLOADED, "Uploaded Image"),
        (SOURCE_TYPED, "Typed Signature"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="captured_signatures",
        null=True,
        blank=True,
        help_text="NULL for one-time external signer signatures",
    )
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default=SOURCE_DRAWN
    )
    # The raw PNG / JPEG of the signature
    image = models.ImageField(upload_to=signature_image_path)

    # For typed signatures store the text and font used
    typed_text = models.CharField(max_length=150, blank=True)
    typed_font = models.CharField(max_length=60, blank=True, default="Dancing Script")

    # The base64 data-URI from the canvas (stored for reference / re-embed)
    image_data_uri = models.TextField(
        blank=True,
        help_text="Base64 PNG data URI from the signature pad",
    )

    is_default = models.BooleanField(
        default=False,
        help_text="User's default/saved signature for future use",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Captured Signature"
        verbose_name_plural = "Captured Signatures"
        ordering = ["-created_at"]

    def __str__(self):
        owner = self.user.get_full_name() if self.user else "External"
        return f"Signature by {owner} ({self.get_source_display()}) – {self.created_at:%Y-%m-%d}"


# ---------------------------------------------------------------------------
# DocumentSigningEvent  (links assignment → signature image + outcome)
# ---------------------------------------------------------------------------


class DocumentSigningEvent(models.Model):
    """
    Records the act of signing (or rejecting) a document.

    This is the immutable record that ties together:
      - Which assignment was fulfilled
      - Which captured signature was used
      - The hash of the document state at the time of signing
      - All forensic metadata
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(
        SignerAssignment,
        on_delete=models.PROTECT,
        related_name="signing_event",
    )
    signature = models.ForeignKey(
        CapturedSignature,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signing_events",
    )

    # Document state at signing time
    document_hash_at_signing = models.CharField(
        max_length=64,
        help_text="SHA-256 of the document file at the moment of signing",
    )

    # Outcome
    action = models.CharField(
        max_length=20,
        choices=[("signed", "Signed"), ("rejected", "Rejected")],
    )
    rejection_reason = models.TextField(blank=True)

    # Forensic
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_info = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # OTP confirmation
    otp_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Document Signing Event"
        verbose_name_plural = "Document Signing Events"
        ordering = ["-timestamp"]

    def __str__(self):
        return (
            f"{self.assignment.display_name} {self.action} "
            f"'{self.assignment.document.title}' at {self.timestamp:%Y-%m-%d %H:%M}"
        )


# ---------------------------------------------------------------------------
# ESignatureAuditLog  (immutable, append-only)
# ---------------------------------------------------------------------------


class ESignatureAuditLog(models.Model):
    """
    Immutable, append-only audit trail for every action taken on a
    SignableDocument.  Records are never updated or deleted.

    This supplements (rather than replaces) the main AuditLog; it stores
    e-signature–specific fields such as document_hash snapshots.
    """

    ACTION_UPLOAD = "upload"
    ACTION_VIEW = "view"
    ACTION_DOWNLOAD = "download"
    ACTION_SIGN = "sign"
    ACTION_REJECT = "reject"
    ACTION_INVITE = "invite"
    ACTION_REMIND = "remind"
    ACTION_REVOKE = "revoke"
    ACTION_CANCEL = "cancel"
    ACTION_EXPIRE = "expire"
    ACTION_OTP_REQUEST = "otp_request"
    ACTION_OTP_VERIFY = "otp_verify"
    ACTION_TAMPER_DETECTED = "tamper_detected"

    ACTION_CHOICES = [
        (ACTION_UPLOAD, "Document Uploaded"),
        (ACTION_VIEW, "Document Viewed"),
        (ACTION_DOWNLOAD, "Document Downloaded"),
        (ACTION_SIGN, "Document Signed"),
        (ACTION_REJECT, "Signature Rejected"),
        (ACTION_INVITE, "Signer Invited"),
        (ACTION_REMIND, "Reminder Sent"),
        (ACTION_REVOKE, "Signer Revoked"),
        (ACTION_CANCEL, "Document Cancelled"),
        (ACTION_EXPIRE, "Document Expired"),
        (ACTION_OTP_REQUEST, "OTP Requested"),
        (ACTION_OTP_VERIFY, "OTP Verified"),
        (ACTION_TAMPER_DETECTED, "Tampering Detected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        SignableDocument,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        db_index=True,
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="esig_audit_logs",
    )
    actor_email = models.EmailField(
        blank=True,
        help_text="Captured at log time; persists if actor user is later deleted",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    detail = models.TextField(blank=True, help_text="Human-readable detail")

    # State snapshot
    document_status_before = models.CharField(max_length=20, blank=True)
    document_status_after = models.CharField(max_length=20, blank=True)
    document_hash_snapshot = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 of the document at this moment",
    )

    # Forensic
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # Related signer (optional)
    related_assignment = models.ForeignKey(
        SignerAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    # Extra structured data
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "E-Signature Audit Log"
        verbose_name_plural = "E-Signature Audit Logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["document", "timestamp"]),
            models.Index(fields=["actor", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["ip_address", "timestamp"]),
        ]
        # Prevent accidental bulk updates/deletes at the DB layer
        # (enforced in the app layer — see save() below)

    def __str__(self):
        actor = self.actor_email or "System"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {actor} – {self.get_action_display()} on {self.document.reference_number}"

    def save(self, *args, **kwargs):
        """Capture actor_email at creation time; block updates."""
        if self.pk:
            # This record already exists — deny changes (immutability)
            raise ValueError(
                "ESignatureAuditLog entries are immutable and cannot be updated."
            )
        if self.actor and not self.actor_email:
            self.actor_email = self.actor.email
        super().save(*args, **kwargs)

    @classmethod
    def record(
        cls,
        document,
        action,
        actor=None,
        actor_email="",
        detail="",
        ip_address=None,
        user_agent="",
        related_assignment=None,
        metadata=None,
        document_hash_snapshot="",
        status_before="",
        status_after="",
    ):
        """Convenience factory — always use this instead of .create() directly."""
        return cls.objects.create(
            document=document,
            actor=actor,
            actor_email=actor_email or (actor.email if actor else ""),
            action=action,
            detail=detail,
            document_status_before=status_before or document.status,
            document_status_after=status_after or document.status,
            document_hash_snapshot=document_hash_snapshot,
            ip_address=ip_address,
            user_agent=user_agent,
            related_assignment=related_assignment,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# DocumentViewer  (access grant for viewers / CC recipients)
# ---------------------------------------------------------------------------


class DocumentViewer(models.Model):
    """Grants read-only access to a SignableDocument for a named viewer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        SignableDocument,
        on_delete=models.CASCADE,
        related_name="viewers",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="viewable_signable_documents",
        null=True,
        blank=True,
    )
    external_email = models.EmailField(blank=True)
    can_download = models.BooleanField(default=False)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="granted_document_views",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["document", "user"]]
        verbose_name = "Document Viewer"
        verbose_name_plural = "Document Viewers"

    def __str__(self):
        who = self.user.email if self.user else self.external_email
        return f"{who} can view '{self.document.title}'"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


# ---------------------------------------------------------------------------
# SigningOTPRecord
# ---------------------------------------------------------------------------


class SigningOTPRecord(models.Model):
    """
    Short-lived OTP issued to a signer immediately before they sign.

    One record per (assignment, request).  Old records are expired by
    the verification view.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        SignerAssignment,
        on_delete=models.CASCADE,
        related_name="otp_records",
    )
    code = models.CharField(max_length=6)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "Signing OTP Record"

    def __str__(self):
        return (
            f"OTP for {self.assignment.display_name} – expires {self.expires_at:%H:%M}"
        )

    @property
    def is_valid(self):
        return not self.used and timezone.now() <= self.expires_at
