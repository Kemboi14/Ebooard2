"""
apps/esignature/serializers.py
──────────────────────────────
Django REST Framework serializers for the e-signature API.

Covers
------
    SignableDocumentSerializer          — full document representation
    SignableDocumentListSerializer      — lightweight list representation
    SignableDocumentUploadSerializer    — create / upload new document
    SignerAssignmentSerializer          — signer details (nested in document)
    SignerAssignmentCreateSerializer    — add a signer to a document
    CapturedSignatureSerializer         — stored signature images
    SigningActionSerializer             — perform sign / reject action
    OTPRequestSerializer                — request a signing OTP
    OTPVerifySerializer                 — verify a signing OTP
    ESignatureAuditLogSerializer        — read-only audit trail entries
    DocumentViewerSerializer            — grant / revoke viewer access
"""

from __future__ import annotations

import base64
import io
import os

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import (
    CapturedSignature,
    DocumentViewer,
    ESignatureAuditLog,
    SignableDocument,
    SignerAssignment,
    SigningOTPRecord,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Reusable field helpers
# ---------------------------------------------------------------------------


class Base64ImageField(serializers.Field):
    """
    Accepts a base64-encoded data URI (``data:image/png;base64,…``) and
    converts it to a Django-compatible in-memory file for saving to an
    ImageField.  On read it returns the data URI stored on the instance.
    """

    MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

    def to_representation(self, value):
        if not value:
            return None
        # Return the data_uri if stored, otherwise the URL of the ImageField
        if hasattr(value, "url"):
            try:
                return value.url
            except ValueError:
                return None
        return value

    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Expected a base64 data URI string.")

        if not data.startswith("data:"):
            raise serializers.ValidationError(
                "Signature image must be a base64 data URI "
                "(e.g. 'data:image/png;base64,…')."
            )

        try:
            header, encoded = data.split(",", 1)
            raw_bytes = base64.b64decode(encoded)
        except Exception:
            raise serializers.ValidationError("Invalid base64 encoding.")

        if len(raw_bytes) > self.MAX_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Signature image exceeds the 2 MB maximum size."
            )

        # Determine extension from MIME type in the header
        if "png" in header:
            ext = ".png"
        elif "jpeg" in header or "jpg" in header:
            ext = ".jpg"
        elif "gif" in header:
            ext = ".gif"
        elif "webp" in header:
            ext = ".webp"
        else:
            ext = ".png"  # default to PNG

        from django.core.files.uploadedfile import InMemoryUploadedFile

        buf = io.BytesIO(raw_bytes)
        return InMemoryUploadedFile(
            file=buf,
            field_name=None,
            name=f"signature{ext}",
            content_type=f"image/{ext.lstrip('.')}",
            size=len(raw_bytes),
            charset=None,
        )


# ---------------------------------------------------------------------------
# User mini-serializer (read-only, embedded in other serializers)
# ---------------------------------------------------------------------------


class SignerUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "job_title", "department"]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name()


# ---------------------------------------------------------------------------
# CapturedSignature
# ---------------------------------------------------------------------------


class CapturedSignatureSerializer(serializers.ModelSerializer):
    """Read representation of a stored signature."""

    source_display = serializers.CharField(source="get_source_display", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CapturedSignature
        fields = [
            "id",
            "source",
            "source_display",
            "typed_text",
            "typed_font",
            "is_default",
            "image_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj):
        request = self.context.get("request")
        try:
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        except (ValueError, AttributeError):
            return None


class CapturedSignatureCreateSerializer(serializers.ModelSerializer):
    """
    Create a new saved signature.  Accepts either:
      - ``image_data_uri``  (base64 PNG from the signature pad canvas)
      - ``image``           (file upload)
    """

    image_data_uri = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Base64 data URI from the signature pad (data:image/png;base64,…)",
    )
    image = Base64ImageField(required=False)

    class Meta:
        model = CapturedSignature
        fields = [
            "id",
            "source",
            "typed_text",
            "typed_font",
            "is_default",
            "image",
            "image_data_uri",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        source = attrs.get("source", CapturedSignature.SOURCE_DRAWN)
        image = attrs.get("image")
        image_data_uri = attrs.get("image_data_uri", "")
        typed_text = attrs.get("typed_text", "")

        if (
            source == CapturedSignature.SOURCE_DRAWN
            and not image
            and not image_data_uri
        ):
            raise serializers.ValidationError(
                "A drawn signature requires either an image upload or a "
                "base64 data URI."
            )
        if source == CapturedSignature.SOURCE_UPLOADED and not image:
            raise serializers.ValidationError(
                "An uploaded signature requires an image file."
            )
        if source == CapturedSignature.SOURCE_TYPED and not typed_text:
            raise serializers.ValidationError(
                "A typed signature requires the 'typed_text' field."
            )

        return attrs

    def create(self, validated_data):
        image_data_uri = validated_data.pop("image_data_uri", "")
        user = self.context["request"].user

        # If user is setting this as default, unset others
        if validated_data.get("is_default"):
            CapturedSignature.objects.filter(user=user, is_default=True).update(
                is_default=False
            )

        instance = CapturedSignature(user=user, **validated_data)
        if image_data_uri:
            instance.image_data_uri = image_data_uri
            # Also decode and save as image file if no explicit image provided
            if not instance.image:
                try:
                    header, encoded = image_data_uri.split(",", 1)
                    raw = base64.b64decode(encoded)
                    ext = ".png" if "png" in header else ".jpg"
                    from django.core.files.base import ContentFile

                    instance.image.save(
                        f"sig_{user.pk}{ext}", ContentFile(raw), save=False
                    )
                except Exception:
                    pass  # image_data_uri stored; image file save is best-effort

        instance.save()
        return instance


# ---------------------------------------------------------------------------
# SignerAssignment
# ---------------------------------------------------------------------------


class SignerAssignmentSerializer(serializers.ModelSerializer):
    """Full read representation of a signer assignment (nested in document)."""

    user_detail = SignerUserSerializer(source="user", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    display_name = serializers.CharField(read_only=True)
    display_email = serializers.CharField(read_only=True)
    signing_url = serializers.SerializerMethodField()
    token_is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = SignerAssignment
        fields = [
            "id",
            "user",
            "user_detail",
            "external_name",
            "external_email",
            "display_name",
            "display_email",
            "signing_order",
            "role",
            "role_display",
            "status",
            "status_display",
            "is_required",
            "placement",
            "otp_verified",
            "otp_verified_at",
            "signed_at",
            "rejected_at",
            "rejection_reason",
            "signed_ip",
            "notified_at",
            "reminder_count",
            "token_is_valid",
            "signing_url",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "signing_token",
            "otp_verified",
            "otp_verified_at",
            "signed_at",
            "rejected_at",
            "signed_ip",
            "notified_at",
            "reminder_count",
            "token_is_valid",
            "signing_url",
            "created_at",
        ]

    def get_signing_url(self, obj):
        request = self.context.get("request")
        path = obj.get_signing_url()
        return request.build_absolute_uri(path) if request else path


class SignerAssignmentCreateSerializer(serializers.ModelSerializer):
    """Add a signer to an existing document."""

    class Meta:
        model = SignerAssignment
        fields = [
            "id",
            "user",
            "external_name",
            "external_email",
            "signing_order",
            "role",
            "is_required",
            "placement",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        user = attrs.get("user")
        external_email = attrs.get("external_email", "")
        external_name = attrs.get("external_name", "")

        if not user and not external_email:
            raise serializers.ValidationError(
                "Either 'user' (system account) or 'external_email' must be provided."
            )
        if not user and not external_name:
            raise serializers.ValidationError(
                "External signers must supply 'external_name'."
            )

        # Validate placement JSON if provided
        placement = attrs.get("placement")
        if placement is not None:
            allowed_keys = {"page", "x", "y", "width", "height"}
            unknown = set(placement.keys()) - allowed_keys
            if unknown:
                raise serializers.ValidationError(
                    {"placement": f"Unknown placement keys: {unknown}"}
                )
            page = placement.get("page", 1)
            if not isinstance(page, int) or page < 1:
                raise serializers.ValidationError(
                    {"placement": "'page' must be a positive integer."}
                )

        return attrs

    def validate_signing_order(self, value):
        document = self.context.get("document")
        if document:
            existing = SignerAssignment.objects.filter(
                document=document, signing_order=value
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    f"Signing order {value} is already taken for this document."
                )
        return value


# ---------------------------------------------------------------------------
# SignableDocument — list serializer (lightweight)
# ---------------------------------------------------------------------------


class SignableDocumentListSerializer(serializers.ModelSerializer):
    """Compact representation for list views."""

    uploaded_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_signers = serializers.IntegerField(read_only=True)
    signed_count = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    file_size_display = serializers.CharField(read_only=True)
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = SignableDocument
        fields = [
            "id",
            "title",
            "reference_number",
            "version",
            "status",
            "status_display",
            "access_level",
            "uploaded_by",
            "uploaded_by_name",
            "branch_name",
            "total_signers",
            "signed_count",
            "completion_percentage",
            "is_expired",
            "expires_at",
            "file_size_display",
            "created_at",
            "finalised_at",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() if obj.uploaded_by else ""

    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else ""


# ---------------------------------------------------------------------------
# SignableDocument — full detail serializer
# ---------------------------------------------------------------------------


class SignableDocumentSerializer(serializers.ModelSerializer):
    """Full document representation including nested signers."""

    uploaded_by_detail = SignerUserSerializer(source="uploaded_by", read_only=True)
    signers = SignerAssignmentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    access_level_display = serializers.CharField(
        source="get_access_level_display", read_only=True
    )
    total_signers = serializers.IntegerField(read_only=True)
    signed_count = serializers.IntegerField(read_only=True)
    completion_percentage = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    file_size_display = serializers.CharField(read_only=True)
    original_file_url = serializers.SerializerMethodField()
    signed_file_url = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    can_download = serializers.SerializerMethodField()
    integrity_verified = serializers.SerializerMethodField()

    class Meta:
        model = SignableDocument
        fields = [
            "id",
            "title",
            "description",
            "reference_number",
            "version",
            "status",
            "status_display",
            "access_level",
            "access_level_display",
            "require_ordered_signing",
            "require_otp",
            "uploaded_by",
            "uploaded_by_detail",
            "branch",
            "branch_name",
            "original_hash",
            "signed_hash",
            "integrity_verified",
            "file_name",
            "file_size",
            "file_size_display",
            "mime_type",
            "expires_at",
            "is_expired",
            "total_signers",
            "signed_count",
            "completion_percentage",
            "signers",
            "original_file_url",
            "signed_file_url",
            "can_download",
            "created_at",
            "updated_at",
            "finalised_at",
        ]
        read_only_fields = [
            "id",
            "reference_number",
            "original_hash",
            "signed_hash",
            "file_name",
            "file_size",
            "mime_type",
            "created_at",
            "updated_at",
            "finalised_at",
        ]

    def get_original_file_url(self, obj):
        """Only expose the original file URL to the uploader and admins."""
        request = self.context.get("request")
        if not request:
            return None
        user = request.user
        if not (
            user == obj.uploaded_by
            or user.role in ("it_administrator", "company_secretary")
        ):
            return None
        try:
            return request.build_absolute_uri(obj.original_file.url)
        except (ValueError, AttributeError):
            return None

    def get_signed_file_url(self, obj):
        request = self.context.get("request")
        if not request or not obj.signed_file:
            return None
        try:
            return request.build_absolute_uri(obj.signed_file.url)
        except (ValueError, AttributeError):
            return None

    def get_branch_name(self, obj):
        return obj.branch.name if obj.branch else ""

    def get_can_download(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        user = request.user
        # Uploader and admins can always download
        if user == obj.uploaded_by or user.role in (
            "it_administrator",
            "company_secretary",
        ):
            return True
        # Signers can download once fully signed
        if obj.status == SignableDocument.STATUS_FULLY_SIGNED:
            if obj.signers.filter(user=user).exists():
                return True
        # Explicit viewer grants
        return obj.viewers.filter(user=user, can_download=True).exists()

    def get_integrity_verified(self, obj):
        """
        Only verify for admins / uploaders to avoid hitting disk on every
        list API call.
        """
        request = self.context.get("request")
        if not request:
            return None
        user = request.user
        if user != obj.uploaded_by and user.role not in (
            "it_administrator",
            "company_secretary",
        ):
            return None
        return obj.verify_original_integrity()


# ---------------------------------------------------------------------------
# SignableDocument — upload / create serializer
# ---------------------------------------------------------------------------


class SignableDocumentUploadSerializer(serializers.ModelSerializer):
    """
    Used for POST /api/esignature/documents/ (file upload endpoint).
    """

    original_file = serializers.FileField(
        help_text="PDF file to upload for signing.  Max 20 MB."
    )
    initial_signers = SignerAssignmentCreateSerializer(
        many=True,
        required=False,
        write_only=True,
        help_text="Optional list of signers to add immediately on upload.",
    )

    class Meta:
        model = SignableDocument
        fields = [
            "id",
            "title",
            "description",
            "original_file",
            "access_level",
            "require_ordered_signing",
            "require_otp",
            "expires_at",
            "branch",
            "initial_signers",
            # Read-back fields
            "reference_number",
            "status",
            "original_hash",
            "file_name",
            "file_size",
            "mime_type",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reference_number",
            "status",
            "original_hash",
            "file_name",
            "file_size",
            "mime_type",
            "created_at",
        ]

    def validate_original_file(self, value):
        max_size = 20 * 1024 * 1024  # 20 MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size ({value.size / 1_048_576:.1f} MB) exceeds the 20 MB limit."
            )

        # Check MIME type — allow only PDFs
        content_type = getattr(value, "content_type", "")
        name_lower = (value.name or "").lower()
        is_pdf = content_type == "application/pdf" or name_lower.endswith(".pdf")
        if not is_pdf:
            raise serializers.ValidationError(
                "Only PDF files are accepted for electronic signing."
            )
        return value

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value

    def create(self, validated_data):
        initial_signers_data = validated_data.pop("initial_signers", [])
        user = self.context["request"].user

        document = SignableDocument.objects.create(uploaded_by=user, **validated_data)

        # Create initial signer assignments
        for signer_data in initial_signers_data:
            SignerAssignment.objects.create(document=document, **signer_data)

        # Advance status: draft → pending once at least one signer is attached
        if initial_signers_data and document.status == SignableDocument.STATUS_DRAFT:
            document.status = SignableDocument.STATUS_PENDING
            document.save(update_fields=["status"])

        return document


# ---------------------------------------------------------------------------
# Signing action serializer (sign or reject)
# ---------------------------------------------------------------------------


class SigningActionSerializer(serializers.Serializer):
    """
    Payload for POST /api/esignature/sign/<token>/.

    The ``action`` field determines sign vs. reject.
    The ``signature_*`` fields capture the actual signature image.
    """

    ACTION_SIGN = "sign"
    ACTION_REJECT = "reject"

    ACTION_CHOICES = [
        (ACTION_SIGN, "Sign"),
        (ACTION_REJECT, "Reject"),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)

    # For sign action — at least one of these must be provided
    signature_data_uri = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Base64 PNG data URI from the signature pad.",
    )
    signature_source = serializers.ChoiceField(
        choices=CapturedSignature.SOURCE_CHOICES,
        default=CapturedSignature.SOURCE_DRAWN,
        required=False,
    )
    saved_signature_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="UUID of a previously saved CapturedSignature to reuse.",
    )
    typed_text = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Text for typed signature.",
    )
    typed_font = serializers.CharField(
        required=False,
        default="Dancing Script",
    )

    # For reject action
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Reason for rejecting the document.",
    )

    # Device / browser metadata (captured by frontend JS)
    device_info = serializers.JSONField(
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        action = attrs.get("action")

        if action == self.ACTION_SIGN:
            has_drawn = bool(attrs.get("signature_data_uri", "").strip())
            has_saved = attrs.get("saved_signature_id") is not None
            has_typed = bool(attrs.get("typed_text", "").strip())

            if not has_drawn and not has_saved and not has_typed:
                raise serializers.ValidationError(
                    "A signature is required. Provide a drawn signature "
                    "(signature_data_uri), a saved signature ID, or typed text."
                )

        if action == self.ACTION_REJECT:
            if not attrs.get("rejection_reason", "").strip():
                raise serializers.ValidationError(
                    {
                        "rejection_reason": "A reason is required when rejecting a document."
                    }
                )

        return attrs


# ---------------------------------------------------------------------------
# OTP serializers
# ---------------------------------------------------------------------------


class OTPRequestSerializer(serializers.Serializer):
    """Request a signing OTP to be sent to the signer's email."""

    # The signing token identifies the assignment; it's in the URL so
    # this serializer body is intentionally empty.  We keep it as a
    # serializer for consistency / future extensibility.
    pass


class OTPVerifySerializer(serializers.Serializer):
    """Verify the 6-digit OTP entered by the signer."""

    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text="6-digit code sent to the signer's email.",
    )

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be a 6-digit numeric code.")
        return value


# ---------------------------------------------------------------------------
# Audit log serializer
# ---------------------------------------------------------------------------


class ESignatureAuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for the e-signature audit trail."""

    action_display = serializers.CharField(source="get_action_display", read_only=True)
    actor_name = serializers.SerializerMethodField()
    document_reference = serializers.CharField(
        source="document.reference_number", read_only=True
    )
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = ESignatureAuditLog
        fields = [
            "id",
            "document",
            "document_reference",
            "document_title",
            "actor",
            "actor_name",
            "actor_email",
            "action",
            "action_display",
            "detail",
            "document_status_before",
            "document_status_after",
            "document_hash_snapshot",
            "ip_address",
            "user_agent",
            "timestamp",
            "related_assignment",
            "metadata",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name()
        return obj.actor_email or "System"


# ---------------------------------------------------------------------------
# Document viewer serializer
# ---------------------------------------------------------------------------


class DocumentViewerSerializer(serializers.ModelSerializer):
    """Grant read-only (or download) access to a named viewer."""

    user_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentViewer
        fields = [
            "id",
            "document",
            "user",
            "user_name",
            "external_email",
            "can_download",
            "granted_by",
            "granted_at",
            "expires_at",
            "is_expired",
        ]
        read_only_fields = ["id", "granted_by", "granted_at", "is_expired"]

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.external_email or ""

    def validate(self, attrs):
        user = attrs.get("user")
        external_email = attrs.get("external_email", "")
        if not user and not external_email:
            raise serializers.ValidationError(
                "Either 'user' or 'external_email' must be provided."
            )
        return attrs


# ---------------------------------------------------------------------------
# Signer invitation serializer (send invitation to a new signer)
# ---------------------------------------------------------------------------


class SignerInvitationSerializer(serializers.Serializer):
    """
    Used by POST /api/esignature/documents/<pk>/invite-signer/

    Creates a SignerAssignment and dispatches the invitation email.
    """

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        help_text="System user to invite (leave blank for external signers).",
    )
    external_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    external_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    signing_order = serializers.IntegerField(min_value=1, default=1)
    role = serializers.ChoiceField(
        choices=SignerAssignment.ROLE_CHOICES,
        default=SignerAssignment.ROLE_SIGNER,
    )
    is_required = serializers.BooleanField(default=True)
    placement = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text=(
            "Signature placement: {page, x, y, width, height} in PDF points. "
            "Defaults to bottom-left of page 1 if omitted."
        ),
    )

    def validate(self, attrs):
        user = attrs.get("user")
        external_email = attrs.get("external_email", "")
        external_name = attrs.get("external_name", "")

        if not user and not external_email:
            raise serializers.ValidationError(
                "Either 'user' (system user ID) or 'external_email' is required."
            )
        if not user and not external_name:
            raise serializers.ValidationError(
                "External signers must include 'external_name'."
            )
        return attrs


# ---------------------------------------------------------------------------
# Document status transition serializer (cancel, re-send, etc.)
# ---------------------------------------------------------------------------


class DocumentStatusSerializer(serializers.Serializer):
    """Simple serializer for status-change actions (cancel, reopen, etc.)."""

    ACTION_CANCEL = "cancel"
    ACTION_REOPEN = "reopen"

    ACTION_CHOICES = [
        (ACTION_CANCEL, "Cancel"),
        (ACTION_REOPEN, "Reopen"),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for this status change.",
    )
