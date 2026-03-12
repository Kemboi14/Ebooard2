"""
apps/esignature/admin.py
────────────────────────
Django admin registration for the e-signature module.

All sensitive fields (original_hash, signed_hash, signing_token) are
read-only.  The audit log is entirely read-only and non-deletable to
preserve the immutable record.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CapturedSignature,
    DocumentViewer,
    ESignatureAuditLog,
    SignableDocument,
    SignerAssignment,
    SigningOTPRecord,
)

# ---------------------------------------------------------------------------
# Inline: SignerAssignment inside SignableDocument
# ---------------------------------------------------------------------------


class SignerAssignmentInline(admin.TabularInline):
    model = SignerAssignment
    extra = 0
    fields = (
        "signing_order",
        "user",
        "external_name",
        "external_email",
        "role",
        "status",
        "is_required",
        "otp_verified",
        "signed_at",
        "signed_ip",
        "reminder_count",
    )
    readonly_fields = (
        "status",
        "otp_verified",
        "signed_at",
        "signed_ip",
        "notified_at",
        "reminder_count",
        "signing_token",
    )
    ordering = ("signing_order",)
    show_change_link = True


class DocumentViewerInline(admin.TabularInline):
    model = DocumentViewer
    extra = 0
    fields = (
        "user",
        "external_email",
        "can_download",
        "granted_by",
        "granted_at",
        "expires_at",
    )
    readonly_fields = ("granted_at",)


class ESignatureAuditLogInline(admin.TabularInline):
    model = ESignatureAuditLog
    extra = 0
    fields = ("timestamp", "actor_email", "action", "detail", "ip_address")
    readonly_fields = fields
    ordering = ("-timestamp",)
    max_num = 20
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# SignableDocument admin
# ---------------------------------------------------------------------------


@admin.register(SignableDocument)
class SignableDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "title",
        "status_badge",
        "uploaded_by",
        "branch",
        "total_signers_display",
        "signed_count_display",
        "completion_bar",
        "created_at",
        "expires_at",
    )
    list_filter = (
        "status",
        "access_level",
        "require_ordered_signing",
        "require_otp",
        "branch",
    )
    search_fields = (
        "title",
        "reference_number",
        "uploaded_by__email",
        "uploaded_by__first_name",
    )
    readonly_fields = (
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
        "integrity_status",
        "completion_bar",
    )
    fieldsets = (
        (
            "Document Identity",
            {
                "fields": (
                    "id",
                    "reference_number",
                    "title",
                    "description",
                    "version",
                    "branch",
                )
            },
        ),
        (
            "Files",
            {
                "fields": (
                    "original_file",
                    "signed_file",
                    "file_name",
                    "file_size",
                    "mime_type",
                    "integrity_status",
                )
            },
        ),
        (
            "Integrity Hashes",
            {
                "classes": ("collapse",),
                "fields": (
                    "original_hash",
                    "signed_hash",
                ),
            },
        ),
        (
            "Workflow",
            {
                "fields": (
                    "status",
                    "access_level",
                    "require_ordered_signing",
                    "require_otp",
                    "expires_at",
                    "completion_bar",
                )
            },
        ),
        (
            "Ownership & Timestamps",
            {
                "fields": (
                    "uploaded_by",
                    "created_at",
                    "updated_at",
                    "finalised_at",
                )
            },
        ),
    )
    inlines = [SignerAssignmentInline, DocumentViewerInline, ESignatureAuditLogInline]
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 25

    # ------------------------------------------------------------------
    # Custom display columns
    # ------------------------------------------------------------------

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            "draft": "#6b7280",
            "pending": "#f59e0b",
            "in_progress": "#3b82f6",
            "fully_signed": "#10b981",
            "rejected": "#ef4444",
            "expired": "#9ca3af",
            "cancelled": "#6b7280",
        }
        colour = colours.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Signers")
    def total_signers_display(self, obj):
        return obj.total_signers

    @admin.display(description="Signed")
    def signed_count_display(self, obj):
        return obj.signed_count

    @admin.display(description="Progress")
    def completion_bar(self, obj):
        pct = obj.completion_percentage
        colour = "#10b981" if pct == 100 else "#3b82f6"
        return format_html(
            '<div style="background:#e5e7eb;border-radius:4px;width:100px;height:10px;">'
            '<div style="background:{};width:{}px;height:10px;border-radius:4px;"></div>'
            "</div> <small>{}%</small>",
            colour,
            pct,
            pct,
        )

    @admin.display(description="Integrity")
    def integrity_status(self, obj):
        if not obj.original_hash:
            return format_html('<span style="color:#9ca3af;">No hash stored</span>')
        try:
            ok = obj.verify_original_integrity()
        except Exception:
            ok = False
        if ok:
            return format_html(
                '<span style="color:#10b981;font-weight:600;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color:#ef4444;font-weight:700;">✗ MISMATCH – possible tampering</span>'
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    actions = ["mark_cancelled", "verify_integrity_action"]

    @admin.action(description="Cancel selected documents")
    def mark_cancelled(self, request, queryset):
        updated = queryset.exclude(status="fully_signed").update(status="cancelled")
        self.message_user(request, f"{updated} document(s) marked as cancelled.")

    @admin.action(description="Verify SHA-256 integrity of selected documents")
    def verify_integrity_action(self, request, queryset):
        ok = 0
        fail = 0
        for doc in queryset:
            try:
                if doc.verify_original_integrity():
                    ok += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
        if fail:
            self.message_user(
                request,
                f"⚠ {fail} document(s) FAILED integrity check.  {ok} passed.",
                level="error",
            )
        else:
            self.message_user(
                request, f"✓ All {ok} document(s) passed integrity check."
            )


# ---------------------------------------------------------------------------
# SignerAssignment admin
# ---------------------------------------------------------------------------


@admin.register(SignerAssignment)
class SignerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "document_ref",
        "display_name",
        "display_email",
        "role",
        "signing_order",
        "status",
        "otp_verified",
        "signed_at",
        "signed_ip",
        "reminder_count",
    )
    list_filter = ("status", "role", "is_required", "otp_verified")
    search_fields = (
        "document__title",
        "document__reference_number",
        "user__email",
        "external_email",
        "external_name",
    )
    readonly_fields = (
        "id",
        "signing_token",
        "otp_verified",
        "otp_verified_at",
        "signed_at",
        "rejected_at",
        "signed_ip",
        "signed_user_agent",
        "signed_device_info",
        "notified_at",
        "reminder_count",
        "reminder_sent_at",
        "created_at",
        "updated_at",
        "token_is_valid_display",
    )
    fieldsets = (
        (
            "Assignment",
            {
                "fields": (
                    "id",
                    "document",
                    "user",
                    "external_name",
                    "external_email",
                    "signing_order",
                    "role",
                    "is_required",
                    "placement",
                )
            },
        ),
        (
            "Secure Token",
            {
                "classes": ("collapse",),
                "fields": (
                    "signing_token",
                    "token_expires_at",
                    "token_is_valid_display",
                ),
            },
        ),
        (
            "OTP",
            {
                "fields": ("otp_verified", "otp_verified_at"),
            },
        ),
        (
            "Outcome",
            {
                "fields": (
                    "status",
                    "signed_at",
                    "rejected_at",
                    "rejection_reason",
                )
            },
        ),
        (
            "Forensics",
            {
                "classes": ("collapse",),
                "fields": (
                    "signed_ip",
                    "signed_user_agent",
                    "signed_device_info",
                ),
            },
        ),
        (
            "Notifications",
            {
                "fields": ("notified_at", "reminder_sent_at", "reminder_count"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    ordering = ("document", "signing_order")
    list_per_page = 30

    @admin.display(description="Document")
    def document_ref(self, obj):
        url = reverse(
            "admin:esignature_signabledocument_change", args=[obj.document.pk]
        )
        return format_html('<a href="{}">{}</a>', url, obj.document.reference_number)

    @admin.display(description="Token valid?", boolean=True)
    def token_is_valid_display(self, obj):
        return obj.token_is_valid


# ---------------------------------------------------------------------------
# CapturedSignature admin
# ---------------------------------------------------------------------------


@admin.register(CapturedSignature)
class CapturedSignatureAdmin(admin.ModelAdmin):
    list_display = ("user", "source", "is_default", "preview_thumb", "created_at")
    list_filter = ("source", "is_default")
    search_fields = ("user__email", "user__first_name", "typed_text")
    readonly_fields = ("id", "created_at", "preview_thumb")
    fields = (
        "id",
        "user",
        "source",
        "image",
        "typed_text",
        "typed_font",
        "is_default",
        "preview_thumb",
        "created_at",
    )
    ordering = ("-created_at",)

    @admin.display(description="Preview")
    def preview_thumb(self, obj):
        try:
            url = obj.image.url
            return format_html(
                '<img src="{}" style="max-height:50px;max-width:120px;'
                'border:1px solid #e5e7eb;border-radius:4px;" />',
                url,
            )
        except (ValueError, AttributeError):
            return "—"


# ---------------------------------------------------------------------------
# ESignatureAuditLog admin  (fully read-only, no delete)
# ---------------------------------------------------------------------------


@admin.register(ESignatureAuditLog)
class ESignatureAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "document_ref",
        "action_badge",
        "actor_email",
        "detail_short",
        "ip_address",
        "document_status_after",
    )
    list_filter = ("action", "document__status")
    search_fields = (
        "document__reference_number",
        "actor_email",
        "actor__email",
        "detail",
        "ip_address",
    )
    readonly_fields = [
        f.name for f in ESignatureAuditLog._meta.get_fields() if hasattr(f, "name")
    ]
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Document")
    def document_ref(self, obj):
        url = reverse(
            "admin:esignature_signabledocument_change",
            args=[obj.document.pk],
        )
        return format_html('<a href="{}">{}</a>', url, obj.document.reference_number)

    @admin.display(description="Action")
    def action_badge(self, obj):
        colours = {
            "upload": "#3b82f6",
            "view": "#6b7280",
            "download": "#8b5cf6",
            "sign": "#10b981",
            "reject": "#ef4444",
            "invite": "#f59e0b",
            "remind": "#f59e0b",
            "revoke": "#f97316",
            "cancel": "#9ca3af",
            "expire": "#9ca3af",
            "otp_request": "#06b6d4",
            "otp_verify": "#06b6d4",
            "tamper_detected": "#dc2626",
        }
        colour = colours.get(obj.action, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colour,
            obj.get_action_display(),
        )

    @admin.display(description="Detail")
    def detail_short(self, obj):
        return obj.detail[:80] + ("…" if len(obj.detail) > 80 else "")


# ---------------------------------------------------------------------------
# SigningOTPRecord admin  (read-only, for support/debugging)
# ---------------------------------------------------------------------------


@admin.register(SigningOTPRecord)
class SigningOTPRecordAdmin(admin.ModelAdmin):
    list_display = (
        "assignment",
        "issued_at",
        "expires_at",
        "used",
        "used_at",
        "is_valid_display",
    )
    list_filter = ("used",)
    search_fields = (
        "assignment__document__reference_number",
        "assignment__external_email",
    )
    readonly_fields = (
        "id",
        "assignment",
        "code",
        "issued_at",
        "expires_at",
        "used",
        "used_at",
    )
    ordering = ("-issued_at",)

    def has_add_permission(self, request):
        return False

    @admin.display(description="Valid?", boolean=True)
    def is_valid_display(self, obj):
        return obj.is_valid


# ---------------------------------------------------------------------------
# DocumentViewer admin
# ---------------------------------------------------------------------------


@admin.register(DocumentViewer)
class DocumentViewerAdmin(admin.ModelAdmin):
    list_display = (
        "document_ref",
        "user",
        "external_email",
        "can_download",
        "granted_by",
        "granted_at",
        "expires_at",
        "is_expired_display",
    )
    list_filter = ("can_download",)
    search_fields = (
        "document__reference_number",
        "user__email",
        "external_email",
    )
    readonly_fields = ("id", "granted_at")
    ordering = ("-granted_at",)

    @admin.display(description="Document")
    def document_ref(self, obj):
        return obj.document.reference_number

    @admin.display(description="Expired?", boolean=True)
    def is_expired_display(self, obj):
        return obj.is_expired
