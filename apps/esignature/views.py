"""
apps/esignature/views.py
────────────────────────
Django template views and Django REST Framework API views for the
electronic signature module.

Template Views (Django)
-----------------------
    DocumentListView            — /esignature/
    DocumentDetailView          — /esignature/<pk>/
    DocumentUploadView          — /esignature/upload/
    SigningInterfaceView        — /esignature/sign/<token>/  (public, token-gated)
    MySignaturesView            — /esignature/my-signatures/
    AuditTrailView              — /esignature/<pk>/audit/

API Views (DRF)
---------------
    DocumentListCreateAPIView       — GET/POST  /api/esignature/documents/
    DocumentRetrieveAPIView         — GET       /api/esignature/documents/<pk>/
    DocumentUploadAPIView           — POST      /api/esignature/documents/upload/
    InviteSignerAPIView             — POST      /api/esignature/documents/<pk>/invite/
    SigningAPIView                  — POST      /api/esignature/sign/<token>/
    OTPRequestAPIView               — POST      /api/esignature/sign/<token>/otp/request/
    OTPVerifyAPIView                — POST      /api/esignature/sign/<token>/otp/verify/
    DocumentDownloadAPIView         — GET       /api/esignature/documents/<pk>/download/
    AuditLogAPIView                 — GET       /api/esignature/documents/<pk>/audit/
    GlobalAuditLogAPIView           — GET       /api/esignature/audit/
    SignerRevokeAPIView             — DELETE    /api/esignature/assignments/<pk>/revoke/
    DocumentStatusAPIView           — POST      /api/esignature/documents/<pk>/status/
    SavedSignatureListCreateAPIView — GET/POST  /api/esignature/my-signatures/
    SavedSignatureDeleteAPIView     — DELETE    /api/esignature/my-signatures/<pk>/
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import string
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView
from rest_framework import generics, permissions, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog

from .models import (
    CapturedSignature,
    DocumentViewer,
    ESignatureAuditLog,
    SignableDocument,
    SignerAssignment,
    SigningOTPRecord,
)
from .serializers import (
    CapturedSignatureCreateSerializer,
    CapturedSignatureSerializer,
    DocumentStatusSerializer,
    DocumentViewerSerializer,
    ESignatureAuditLogSerializer,
    OTPVerifySerializer,
    SignableDocumentListSerializer,
    SignableDocumentSerializer,
    SignableDocumentUploadSerializer,
    SignerAssignmentCreateSerializer,
    SignerInvitationSerializer,
    SigningActionSerializer,
)

logger = logging.getLogger("esignature.views")


# ============================================================================
# Helpers / decorators
# ============================================================================


def _get_client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _get_user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:500]


def _record_audit(
    document,
    action: str,
    request=None,
    actor=None,
    detail: str = "",
    assignment=None,
    status_before: str = "",
    status_after: str = "",
):
    """Create an immutable ESignatureAuditLog entry."""
    ip = _get_client_ip(request) if request else None
    ua = _get_user_agent(request) if request else ""
    if actor is None and request and request.user.is_authenticated:
        actor = request.user

    try:
        ESignatureAuditLog.record(
            document=document,
            action=action,
            actor=actor,
            detail=detail,
            ip_address=ip,
            user_agent=ua,
            related_assignment=assignment,
            status_before=status_before,
            status_after=status_after,
        )
    except Exception as exc:
        logger.warning("Audit log failed for action %s: %s", action, exc)


def _can_manage_document(user, document: SignableDocument) -> bool:
    """
    Returns True if the user is allowed to manage (invite signers,
    cancel, download originals, etc.) a document.
    """
    if user.role in ("it_administrator", "company_secretary"):
        return True
    return user == document.uploaded_by


def _can_view_document(user, document: SignableDocument) -> bool:
    """
    Returns True if the user has any viewing right over the document.
    """
    if _can_manage_document(user, document):
        return True
    # Is a signer?
    if document.signers.filter(user=user).exists():
        return True
    # Has an explicit viewer grant?
    if document.viewers.filter(user=user).exists():
        return True
    return False


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _issue_signing_otp(assignment: SignerAssignment) -> SigningOTPRecord:
    """
    Expire any old unused OTPs for this assignment, create a new one,
    and return it.
    """
    # Expire previous unused records
    SigningOTPRecord.objects.filter(
        assignment=assignment,
        used=False,
    ).update(expires_at=timezone.now())

    expires_at = timezone.now() + timedelta(minutes=10)
    return SigningOTPRecord.objects.create(
        assignment=assignment,
        code=_generate_otp(),
        expires_at=expires_at,
    )


# ============================================================================
# DRF permission classes
# ============================================================================


class IsDocumentManager(permissions.BasePermission):
    """
    Object-level: allows access only to the uploader or IT admin /
    company secretary.
    """

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, SignableDocument):
            return _can_manage_document(request.user, obj)
        return False


class IsDocumentViewer(permissions.BasePermission):
    """Object-level: allows access to anyone with viewing rights."""

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, SignableDocument):
            return _can_view_document(request.user, obj)
        return False


class CanViewAuditLogs(permissions.BasePermission):
    """Allows access only to roles with audit viewing rights."""

    ALLOWED_ROLES = (
        "it_administrator",
        "company_secretary",
        "internal_audit",
        "compliance_officer",
    )

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in self.ALLOWED_ROLES


# ============================================================================
# ─── TEMPLATE VIEWS ─────────────────────────────────────────────────────────
# ============================================================================


class DocumentListView(LoginRequiredMixin, ListView):
    """
    /esignature/
    Lists all signable documents visible to the current user.
    """

    template_name = "esignature/document_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = SignableDocument.objects.select_related(
            "uploaded_by", "branch"
        ).prefetch_related("signers")

        if user.role in ("it_administrator", "company_secretary"):
            # Admins see everything
            pass
        else:
            from django.db.models import Q

            qs = qs.filter(
                Q(uploaded_by=user) | Q(signers__user=user) | Q(viewers__user=user)
            ).distinct()

        # Filters from query params
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)

        search = self.request.GET.get("q", "").strip()
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(title__icontains=search) | Q(reference_number__icontains=search)
            )

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        ctx["page_title"] = "E-Signatures"
        ctx["status_filter"] = self.request.GET.get("status", "")
        ctx["search_query"] = self.request.GET.get("q", "")
        ctx["status_choices"] = SignableDocument.STATUS_CHOICES

        # Stats for the current user
        if user.role in ("it_administrator", "company_secretary"):
            base_qs = SignableDocument.objects
        else:
            from django.db.models import Q

            base_qs = SignableDocument.objects.filter(
                Q(uploaded_by=user) | Q(signers__user=user) | Q(viewers__user=user)
            ).distinct()

        ctx["stats"] = {
            "total": base_qs.count(),
            "pending": base_qs.filter(
                status__in=["draft", "pending", "in_progress"]
            ).count(),
            "fully_signed": base_qs.filter(status="fully_signed").count(),
            "awaiting_my_signature": SignerAssignment.objects.filter(
                user=user,
                status__in=["pending", "notified", "viewed"],
            ).count(),
        }

        ctx["can_upload"] = user.role in (
            "it_administrator",
            "company_secretary",
            "compliance_officer",
            "executive_management",
        )
        return ctx


class DocumentDetailView(LoginRequiredMixin, DetailView):
    """
    /esignature/<pk>/
    Full document view with signers, status, audit trail preview.
    """

    model = SignableDocument
    template_name = "esignature/document_detail.html"
    context_object_name = "document"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not _can_view_document(request.user, obj):
            messages.error(request, "You do not have access to this document.")
            return redirect("esignature:document_list")

        # Record view event
        _record_audit(
            document=obj,
            action=ESignatureAuditLog.ACTION_VIEW,
            request=request,
            detail=f"Document viewed by {request.user.email}",
        )
        # Also update assignment status to "viewed" if this user is a pending signer
        SignerAssignment.objects.filter(
            document=obj,
            user=request.user,
            status__in=[
                SignerAssignment.STATUS_PENDING,
                SignerAssignment.STATUS_NOTIFIED,
            ],
        ).update(status=SignerAssignment.STATUS_VIEWED)

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return SignableDocument.objects.select_related(
            "uploaded_by", "branch"
        ).prefetch_related(
            "signers__user",
            "signers__signing_event__signature",
            "viewers__user",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        document = self.object
        user = self.request.user

        ctx["page_title"] = document.title
        ctx["can_manage"] = _can_manage_document(user, document)

        # My assignment for this document (if any)
        ctx["my_assignment"] = document.signers.filter(user=user).first()

        # Recent audit trail (last 10 entries)
        ctx["recent_audit"] = document.audit_logs.order_by("-timestamp")[:10]

        # Integrity check (only for managers)
        if ctx["can_manage"]:
            ctx["integrity_ok"] = document.verify_original_integrity()
        else:
            ctx["integrity_ok"] = None

        # Determine whether the signed file is downloadable by this user
        can_dl = False
        if _can_manage_document(user, document):
            can_dl = True
        elif document.status == SignableDocument.STATUS_FULLY_SIGNED:
            if document.signers.filter(user=user).exists():
                can_dl = True
            elif document.viewers.filter(user=user, can_download=True).exists():
                can_dl = True
        ctx["can_download"] = can_dl

        return ctx


class DocumentUploadView(LoginRequiredMixin, View):
    """
    /esignature/upload/
    GET  — render the upload form
    POST — handle file upload + signer setup
    """

    ALLOWED_ROLES = (
        "it_administrator",
        "company_secretary",
        "compliance_officer",
        "executive_management",
    )
    template_name = "esignature/document_upload.html"

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.role not in self.ALLOWED_ROLES
        ):
            messages.error(
                request, "You do not have permission to upload documents for signing."
            )
            return redirect("esignature:document_list")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from apps.accounts.models import User

        ctx = {
            "page_title": "Upload Document for Signing",
            "all_users": User.objects.filter(is_active=True).order_by(
                "first_name", "last_name"
            ),
            "access_choices": SignableDocument.ACCESS_LEVEL_CHOICES,
        }
        # Branch context
        try:
            from apps.agencies.models import Branch

            if request.user.role == "it_administrator":
                ctx["branches"] = Branch.objects.filter(is_active=True).order_by("name")
            else:
                from apps.agencies.models import UserBranchMembership

                memberships = UserBranchMembership.objects.filter(
                    user=request.user, is_active=True
                ).select_related("branch")
                ctx["branches"] = [m.branch for m in memberships]
        except Exception:
            ctx["branches"] = []

        return render(request, self.template_name, ctx)

    def post(self, request):
        from apps.accounts.models import User as UserModel

        post = request.POST

        # ------------------------------------------------------------------
        # Parse flat signer fields (signer_user_0, signer_role_0, …) into
        # the nested list that SignableDocumentUploadSerializer expects.
        # ------------------------------------------------------------------
        signer_count = 0
        try:
            signer_count = int(post.get("signer_count", 0))
        except (TypeError, ValueError):
            pass

        initial_signers = []
        for i in range(signer_count):
            user_id = post.get(f"signer_user_{i}", "").strip()
            ext_name = post.get(f"signer_name_{i}", "").strip()
            ext_email = post.get(f"signer_email_{i}", "").strip()
            role = post.get(f"signer_role_{i}", "signer").strip()
            required_raw = post.get(f"signer_required_{i}", "true").strip().lower()
            is_required = required_raw in ("true", "1", "yes", "on")

            signer_entry = {
                "signing_order": i + 1,
                "role": role,
                "is_required": is_required,
            }
            if user_id:
                signer_entry["user"] = user_id
            else:
                signer_entry["external_name"] = ext_name
                signer_entry["external_email"] = ext_email

            # Only include signer if minimally filled in
            if user_id or ext_email:
                initial_signers.append(signer_entry)

        # ------------------------------------------------------------------
        # HTML checkboxes only appear in POST when checked; coerce to bool.
        # ------------------------------------------------------------------
        require_ordered = post.get("require_ordered_signing", "") in (
            "true",
            "on",
            "1",
            "True",
        )
        require_otp = post.get("require_otp", "") in (
            "true",
            "on",
            "1",
            "True",
        )

        # ------------------------------------------------------------------
        # Build the data dict for the serializer.
        # ------------------------------------------------------------------
        data = {
            "title": post.get("title", "").strip(),
            "description": post.get("description", "").strip(),
            "access_level": post.get("access_level", "private"),
            "require_ordered_signing": require_ordered,
            "require_otp": require_otp,
            "original_file": request.FILES.get("original_file"),
            "initial_signers": initial_signers,
        }

        # Optional fields
        branch_val = post.get("branch", "").strip()
        if branch_val:
            data["branch"] = branch_val

        expires_at_val = post.get("expires_at", "").strip()
        if expires_at_val:
            data["expires_at"] = expires_at_val

        serializer = SignableDocumentUploadSerializer(
            data=data,
            context={"request": request},
        )

        if serializer.is_valid():
            document = serializer.save()

            _record_audit(
                document=document,
                action=ESignatureAuditLog.ACTION_UPLOAD,
                request=request,
                detail=(
                    f"Document '{document.title}' uploaded. "
                    f"SHA-256: {document.original_hash[:16]}…"
                ),
                status_after=document.status,
            )

            AuditLog.log_action(
                user=request.user,
                action="upload",
                description=f"E-Signature document uploaded: {document.title}",
                module="documents",
                severity="low",
                content_object=document,
                ip_address=_get_client_ip(request),
                user_agent=_get_user_agent(request),
            )

            # Notify first signer immediately if document moves to pending
            if document.status in (
                SignableDocument.STATUS_PENDING,
                SignableDocument.STATUS_IN_PROGRESS,
            ):
                first_signer = document.next_signer
                if first_signer:
                    try:
                        from .tasks import send_signing_invitation

                        send_signing_invitation.delay(str(first_signer.pk))
                    except Exception:
                        logger.warning(
                            "Could not queue signing invitation for signer %s",
                            first_signer.pk,
                        )

            messages.success(
                request,
                f"Document '{document.title}' uploaded successfully. "
                f"Reference: {document.reference_number}",
            )
            return redirect("esignature:document_detail", pk=document.pk)

        # ------------------------------------------------------------------
        # Validation failed — re-render the form with errors.
        # ------------------------------------------------------------------
        ctx = {
            "page_title": "Upload Document for Signing",
            "errors": serializer.errors,
            "form_data": post,
            "all_users": UserModel.objects.filter(is_active=True).order_by(
                "first_name", "last_name"
            ),
            "access_choices": SignableDocument.ACCESS_LEVEL_CHOICES,
        }
        try:
            from apps.agencies.models import Branch

            if request.user.role == "it_administrator":
                ctx["branches"] = Branch.objects.filter(is_active=True).order_by("name")
            else:
                from apps.agencies.models import UserBranchMembership

                memberships = UserBranchMembership.objects.filter(
                    user=request.user, is_active=True
                ).select_related("branch")
                ctx["branches"] = [m.branch for m in memberships]
        except Exception:
            ctx["branches"] = []

        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, ctx)


class SigningInterfaceView(View):
    """
    /esignature/sign/<token>/

    The public-facing signing page.  Accessible via the token link in the
    invitation email.  The signer does NOT need to be logged in to reach
    this view, but if they are logged in the view will try to match them
    to the assignment.

    Workflow:
      1.  Validate the signing token.
      2.  If OTP is required and not yet verified → show OTP verification step.
      3.  Otherwise → show the signing pad interface.
      4.  On POST: capture signature / rejection.
    """

    template_name = "esignature/signing_interface.html"

    def _get_assignment(self, token) -> SignerAssignment:
        return get_object_or_404(
            SignerAssignment.objects.select_related("document", "user"),
            signing_token=token,
        )

    def dispatch(self, request, *args, **kwargs):
        token = kwargs.get("token")
        assignment = self._get_assignment(token)

        # Token validity check
        if not assignment.token_is_valid:
            return render(
                request,
                "esignature/signing_invalid.html",
                {
                    "reason": assignment.status,
                    "document": assignment.document,
                },
                status=410,
            )

        # Document expiry check
        if assignment.document.is_expired:
            return render(
                request,
                "esignature/signing_invalid.html",
                {
                    "reason": "expired",
                    "document": assignment.document,
                },
                status=410,
            )

        # Ordered signing: check if it's this signer's turn
        doc = assignment.document
        if doc.require_ordered_signing:
            next_signer = doc.next_signer
            if next_signer and next_signer.pk != assignment.pk:
                return render(
                    request,
                    "esignature/signing_not_yet.html",
                    {
                        "assignment": assignment,
                        "document": doc,
                        "current_signer_name": next_signer.display_name,
                    },
                )

        self._assignment = assignment
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, token):
        assignment = self._assignment
        document = assignment.document

        # Update status to "viewed" if still pending / notified
        if assignment.status in (
            SignerAssignment.STATUS_PENDING,
            SignerAssignment.STATUS_NOTIFIED,
        ):
            assignment.status = SignerAssignment.STATUS_VIEWED
            assignment.save(update_fields=["status"])

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_VIEW,
            request=request,
            actor=assignment.user if assignment.user else None,
            detail=f"Signing page viewed by {assignment.display_email}",
            assignment=assignment,
        )

        ctx = {
            "assignment": assignment,
            "document": document,
            "page_title": f"Sign: {document.title}",
            "require_otp": document.require_otp,
            "otp_verified": assignment.otp_verified,
            "show_signing_pad": (not document.require_otp or assignment.otp_verified),
        }

        # If user has saved signatures, offer them as options
        if request.user.is_authenticated:
            ctx["saved_signatures"] = CapturedSignature.objects.filter(
                user=request.user
            ).order_by("-is_default", "-created_at")[:5]
        else:
            ctx["saved_signatures"] = []

        return render(request, self.template_name, ctx)

    def post(self, request, token):
        assignment = self._assignment
        document = assignment.document

        action = request.POST.get("action", "").strip()

        # ── OTP verification step ────────────────────────────────────────
        if action == "verify_otp":
            return self._handle_otp_verify(request, assignment)

        # ── Request a new OTP ────────────────────────────────────────────
        if action == "request_otp":
            return self._handle_otp_request(request, assignment)

        # ── Sign ─────────────────────────────────────────────────────────
        if action == "sign":
            # Must have OTP verified if document requires it
            if document.require_otp and not assignment.otp_verified:
                messages.error(
                    request, "Please complete OTP verification before signing."
                )
                return redirect(request.path)
            return self._handle_sign(request, assignment)

        # ── Reject ───────────────────────────────────────────────────────
        if action == "reject":
            return self._handle_reject(request, assignment)

        messages.error(request, "Invalid action.")
        return redirect(request.path)

    # ------------------------------------------------------------------
    # Sub-handlers
    # ------------------------------------------------------------------

    def _handle_otp_request(self, request, assignment):
        otp_record = _issue_signing_otp(assignment)

        # Send via Celery task
        from .tasks import send_otp_email

        send_otp_email.delay(str(otp_record.pk))

        _record_audit(
            document=assignment.document,
            action=ESignatureAuditLog.ACTION_OTP_REQUEST,
            request=request,
            actor=assignment.user,
            detail=f"OTP requested for {assignment.display_email}",
            assignment=assignment,
        )
        messages.info(
            request,
            f"A verification code has been sent to {assignment.display_email}. "
            "It is valid for 10 minutes.",
        )
        return redirect(request.path)

    def _handle_otp_verify(self, request, assignment):
        code = request.POST.get("otp_code", "").strip()
        if not code:
            messages.error(request, "Please enter the verification code.")
            return redirect(request.path)

        otp_record = (
            SigningOTPRecord.objects.filter(
                assignment=assignment,
                used=False,
            )
            .order_by("-issued_at")
            .first()
        )

        if not otp_record or not otp_record.is_valid:
            messages.error(
                request,
                "Your verification code has expired. Please request a new one.",
            )
            return redirect(request.path)

        if otp_record.code != code:
            _record_audit(
                document=assignment.document,
                action=ESignatureAuditLog.ACTION_OTP_REQUEST,
                request=request,
                detail=f"OTP verification failed for {assignment.display_email}",
                assignment=assignment,
            )
            messages.error(request, "Invalid verification code. Please try again.")
            return redirect(request.path)

        # Mark OTP as used
        otp_record.used = True
        otp_record.used_at = timezone.now()
        otp_record.save(update_fields=["used", "used_at"])

        # Mark assignment as OTP-verified
        assignment.otp_verified = True
        assignment.otp_verified_at = timezone.now()
        assignment.status = SignerAssignment.STATUS_OTP_VERIFIED
        assignment.save(update_fields=["otp_verified", "otp_verified_at", "status"])

        _record_audit(
            document=assignment.document,
            action=ESignatureAuditLog.ACTION_OTP_VERIFY,
            request=request,
            detail=f"OTP verified for {assignment.display_email}",
            assignment=assignment,
        )
        messages.success(request, "Identity verified. You may now sign the document.")
        return redirect(request.path)

    def _handle_sign(self, request, assignment):
        document = assignment.document

        signature_data_uri = request.POST.get("signature_data_uri", "").strip()
        typed_text = request.POST.get("typed_text", "").strip()
        saved_sig_id = request.POST.get("saved_signature_id", "").strip()
        source = request.POST.get("signature_source", CapturedSignature.SOURCE_DRAWN)

        if not signature_data_uri and not typed_text and not saved_sig_id:
            messages.error(request, "Please provide your signature before submitting.")
            return redirect(request.path)

        # Resolve or create the CapturedSignature
        captured_sig = None

        if saved_sig_id:
            try:
                captured_sig = CapturedSignature.objects.get(
                    pk=saved_sig_id,
                    user=request.user if request.user.is_authenticated else None,
                )
            except CapturedSignature.DoesNotExist:
                messages.error(request, "Saved signature not found.")
                return redirect(request.path)

        elif signature_data_uri:
            import base64
            import io as _io

            from django.core.files.base import ContentFile

            try:
                header, encoded = signature_data_uri.split(",", 1)
                raw_bytes = base64.b64decode(encoded)
                ext = ".png" if "png" in header else ".jpg"
                content_file = ContentFile(raw_bytes, name=f"sig{ext}")

                captured_sig = CapturedSignature(
                    user=request.user if request.user.is_authenticated else None,
                    source=source,
                    image_data_uri=signature_data_uri,
                )
                captured_sig.image.save(f"sig{ext}", content_file, save=False)
                captured_sig.save()
            except Exception as exc:
                logger.error("Failed to save signature image: %s", exc)
                messages.error(
                    request, "Failed to process your signature. Please try again."
                )
                return redirect(request.path)

        elif typed_text:
            from django.core.files.base import ContentFile

            captured_sig = CapturedSignature(
                user=request.user if request.user.is_authenticated else None,
                source=CapturedSignature.SOURCE_TYPED,
                typed_text=typed_text,
                typed_font=request.POST.get("typed_font", "Dancing Script"),
            )
            # Generate a simple typed-signature image with ReportLab
            try:
                sig_img_bytes = _render_typed_signature(typed_text)
                captured_sig.image.save(
                    "typed_sig.png", ContentFile(sig_img_bytes), save=False
                )
                captured_sig.image_data_uri = (
                    "data:image/png;base64,"
                    + __import__("base64").b64encode(sig_img_bytes).decode()
                )
            except Exception:
                pass
            captured_sig.save()

        # Snapshot the document hash at signing time
        doc_hash_at_sign = document.original_hash

        # Create the DocumentSigningEvent
        from .models import DocumentSigningEvent

        ip = _get_client_ip(request)
        ua = _get_user_agent(request)

        device_info = {
            "user_agent": ua,
            "ip": ip,
        }

        event = DocumentSigningEvent.objects.create(
            assignment=assignment,
            signature=captured_sig,
            document_hash_at_signing=doc_hash_at_sign,
            action="signed",
            ip_address=ip,
            user_agent=ua,
            device_info=device_info,
            otp_used=assignment.otp_verified,
        )

        # Update the assignment
        assignment.status = SignerAssignment.STATUS_SIGNED
        assignment.signed_at = timezone.now()
        assignment.signed_ip = ip
        assignment.signed_user_agent = ua
        assignment.signed_device_info = device_info
        assignment.save(
            update_fields=[
                "status",
                "signed_at",
                "signed_ip",
                "signed_user_agent",
                "signed_device_info",
            ]
        )

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_SIGN,
            request=request,
            actor=assignment.user,
            detail=f"{assignment.display_name} signed the document",
            assignment=assignment,
            document_hash_snapshot=doc_hash_at_sign,
        )

        # Also log to global audit trail
        AuditLog.log_action(
            user=assignment.user,
            action="approve",
            description=f"Document signed: {document.title} [{document.reference_number}]",
            module="documents",
            severity="medium",
            ip_address=ip,
            user_agent=ua,
        )

        # Update document status
        old_status = document.status
        _check_and_advance_document(document)

        messages.success(
            request,
            f"You have successfully signed '{document.title}'. "
            "The document owner has been notified.",
        )

        # If ordered: notify next signer
        if (
            document.require_ordered_signing
            and document.status == SignableDocument.STATUS_IN_PROGRESS
        ):
            next_signer = document.next_signer
            if next_signer:
                from .tasks import send_signing_invitation

                send_signing_invitation.delay(str(next_signer.pk))

        return render(
            request,
            "esignature/signing_complete.html",
            {
                "assignment": assignment,
                "document": document,
                "page_title": "Document Signed",
            },
        )

    def _handle_reject(self, request, assignment):
        reason = request.POST.get("rejection_reason", "").strip()
        if not reason:
            messages.error(
                request,
                "Please provide a reason for rejecting the document.",
            )
            return redirect(request.path)

        document = assignment.document
        ip = _get_client_ip(request)

        assignment.status = SignerAssignment.STATUS_REJECTED
        assignment.rejected_at = timezone.now()
        assignment.rejection_reason = reason
        assignment.signed_ip = ip
        assignment.save(
            update_fields=["status", "rejected_at", "rejection_reason", "signed_ip"]
        )

        # Update document status to rejected
        old_status = document.status
        document.status = SignableDocument.STATUS_REJECTED
        document.save(update_fields=["status"])

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_REJECT,
            request=request,
            actor=assignment.user,
            detail=f"{assignment.display_name} rejected. Reason: {reason}",
            assignment=assignment,
            status_before=old_status,
            status_after=SignableDocument.STATUS_REJECTED,
        )

        # Notify the document owner
        from .tasks import send_rejection_notification

        send_rejection_notification.delay(str(assignment.pk))

        return render(
            request,
            "esignature/signing_rejected.html",
            {
                "assignment": assignment,
                "document": document,
                "page_title": "Signature Rejected",
            },
        )


class MySignaturesView(LoginRequiredMixin, TemplateView):
    """
    /esignature/my-signatures/
    Personal dashboard: documents awaiting my signature + my activity.
    """

    template_name = "esignature/my_signatures.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Assignments pending my action
        ctx["pending_assignments"] = (
            SignerAssignment.objects.filter(
                user=user,
                status__in=[
                    SignerAssignment.STATUS_PENDING,
                    SignerAssignment.STATUS_NOTIFIED,
                    SignerAssignment.STATUS_VIEWED,
                    SignerAssignment.STATUS_OTP_VERIFIED,
                ],
            )
            .select_related("document")
            .order_by("document__expires_at", "signing_order")
        )

        # Completed / rejected assignments
        ctx["completed_assignments"] = (
            SignerAssignment.objects.filter(
                user=user,
                status__in=[
                    SignerAssignment.STATUS_SIGNED,
                    SignerAssignment.STATUS_REJECTED,
                ],
            )
            .select_related("document")
            .order_by("-signed_at", "-rejected_at")[:20]
        )

        # Saved signatures
        ctx["saved_signatures"] = CapturedSignature.objects.filter(user=user).order_by(
            "-is_default", "-created_at"
        )

        ctx["page_title"] = "My E-Signatures"
        return ctx


class AuditTrailView(LoginRequiredMixin, DetailView):
    """
    /esignature/<pk>/audit/
    Full immutable audit trail for a single document.
    """

    model = SignableDocument
    template_name = "esignature/audit_trail.html"
    context_object_name = "document"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        allowed_roles = (
            "it_administrator",
            "company_secretary",
            "internal_audit",
            "compliance_officer",
        )
        if not (request.user.role in allowed_roles or request.user == obj.uploaded_by):
            messages.error(
                request,
                "You do not have permission to view the audit trail for this document.",
            )
            return redirect("esignature:document_detail", pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        document = self.object

        audit_qs = document.audit_logs.select_related(
            "actor", "related_assignment"
        ).order_by("-timestamp")

        paginator = Paginator(audit_qs, 25)
        page_number = self.request.GET.get("page", 1)
        ctx["audit_page"] = paginator.get_page(page_number)
        ctx["page_title"] = f"Audit Trail – {document.title}"
        return ctx


# ============================================================================
# ─── DRF API VIEWS ──────────────────────────────────────────────────────────
# ============================================================================


class DocumentListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/esignature/documents/     — list documents visible to the user
    POST /api/esignature/documents/     — upload a new document (multipart)
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SignableDocumentUploadSerializer
        return SignableDocumentListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = SignableDocument.objects.select_related(
            "uploaded_by", "branch"
        ).prefetch_related("signers")

        if user.role in ("it_administrator", "company_secretary"):
            pass
        else:
            from django.db.models import Q

            qs = qs.filter(
                Q(uploaded_by=user) | Q(signers__user=user) | Q(viewers__user=user)
            ).distinct()

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        document = serializer.save()
        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_UPLOAD,
            request=self.request,
            detail=f"Document uploaded via API. Hash: {document.original_hash[:16]}…",
            status_after=document.status,
        )


class DocumentRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/esignature/documents/<pk>/   — full document detail
    PATCH /api/esignature/documents/<pk>/   — update title / description / access
    """

    permission_classes = [permissions.IsAuthenticated, IsDocumentViewer]
    serializer_class = SignableDocumentSerializer

    def get_queryset(self):
        return SignableDocument.objects.select_related(
            "uploaded_by", "branch"
        ).prefetch_related(
            "signers__user",
            "viewers__user",
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        _record_audit(
            document=instance,
            action=ESignatureAuditLog.ACTION_VIEW,
            request=request,
            detail="Document detail retrieved via API",
        )
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _can_manage_document(request.user, instance):
            return Response(
                {"detail": "You do not have permission to update this document."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)


class InviteSignerAPIView(APIView):
    """
    POST /api/esignature/documents/<pk>/invite/

    Add a signer to a document and send them the invitation email.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(SignableDocument, pk=pk)

        if not _can_manage_document(request.user, document):
            return Response(
                {"detail": "You do not have permission to invite signers."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if document.status in (
            SignableDocument.STATUS_FULLY_SIGNED,
            SignableDocument.STATUS_CANCELLED,
            SignableDocument.STATUS_REJECTED,
            SignableDocument.STATUS_EXPIRED,
        ):
            return Response(
                {
                    "detail": f"Cannot invite signers to a document in '{document.status}' status."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SignerInvitationSerializer(
            data=request.data,
            context={"request": request, "document": document},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data

        # Create the assignment
        assignment = SignerAssignment.objects.create(
            document=document,
            user=vd.get("user"),
            external_name=vd.get("external_name", ""),
            external_email=vd.get("external_email", ""),
            signing_order=vd.get("signing_order", 1),
            role=vd.get("role", SignerAssignment.ROLE_SIGNER),
            is_required=vd.get("is_required", True),
            placement=vd.get("placement"),
            token_expires_at=document.expires_at,
        )

        # Advance document status if still draft
        if document.status == SignableDocument.STATUS_DRAFT:
            document.status = SignableDocument.STATUS_PENDING
            document.save(update_fields=["status"])

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_INVITE,
            request=request,
            detail=f"Signer invited: {assignment.display_name} <{assignment.display_email}>",
            assignment=assignment,
        )

        # Send invitation email (async)
        # For ordered signing, only send if it's their turn
        should_send = True
        if document.require_ordered_signing:
            next_signer = document.next_signer
            should_send = next_signer and next_signer.pk == assignment.pk

        if should_send:
            from .tasks import send_signing_invitation

            send_signing_invitation.delay(str(assignment.pk))

        out = SignerAssignmentCreateSerializer(
            assignment,
            context={"request": request},
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class SigningAPIView(APIView):
    """
    POST /api/esignature/sign/<token>/

    API endpoint for signing or rejecting a document.
    Used by the JS frontend (HTMX / fetch) within the signing interface.
    """

    permission_classes = []  # Token-based access; no session required

    def post(self, request, token):
        assignment = get_object_or_404(
            SignerAssignment.objects.select_related("document", "user"),
            signing_token=token,
        )

        if not assignment.token_is_valid:
            return Response(
                {
                    "detail": "This signing link is no longer valid.",
                    "reason": assignment.status,
                },
                status=status.HTTP_410_GONE,
            )

        if assignment.document.is_expired:
            return Response(
                {"detail": "This document has expired."},
                status=status.HTTP_410_GONE,
            )

        serializer = SigningActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data
        action = vd["action"]

        if action == SigningActionSerializer.ACTION_SIGN:
            return self._do_sign(request, assignment, vd)
        else:
            return self._do_reject(request, assignment, vd)

    def _do_sign(self, request, assignment, vd):
        document = assignment.document

        if document.require_otp and not assignment.otp_verified:
            return Response(
                {"detail": "OTP verification is required before signing."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ip = _get_client_ip(request)
        ua = _get_user_agent(request)

        # Resolve / create captured signature
        captured_sig = self._resolve_signature(request, assignment, vd)
        if captured_sig is None:
            return Response(
                {"detail": "Failed to process signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Signing event
        from .models import DocumentSigningEvent

        DocumentSigningEvent.objects.create(
            assignment=assignment,
            signature=captured_sig,
            document_hash_at_signing=document.original_hash,
            action="signed",
            ip_address=ip,
            user_agent=ua,
            device_info=vd.get("device_info"),
            otp_used=assignment.otp_verified,
        )

        # Update assignment
        assignment.status = SignerAssignment.STATUS_SIGNED
        assignment.signed_at = timezone.now()
        assignment.signed_ip = ip
        assignment.signed_user_agent = ua
        assignment.signed_device_info = vd.get("device_info")
        assignment.save(
            update_fields=[
                "status",
                "signed_at",
                "signed_ip",
                "signed_user_agent",
                "signed_device_info",
            ]
        )

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_SIGN,
            request=request,
            actor=assignment.user,
            detail=f"{assignment.display_name} signed via API",
            assignment=assignment,
        )

        _check_and_advance_document(document)

        # Trigger next signer notification if ordered
        if (
            document.require_ordered_signing
            and document.status == SignableDocument.STATUS_IN_PROGRESS
        ):
            next_signer = document.next_signer
            if next_signer:
                from .tasks import send_signing_invitation

                send_signing_invitation.delay(str(next_signer.pk))

        return Response(
            {
                "status": "signed",
                "document_status": document.status,
                "message": "Document signed successfully.",
            }
        )

    def _do_reject(self, request, assignment, vd):
        document = assignment.document
        reason = vd.get("rejection_reason", "")
        ip = _get_client_ip(request)

        old_status = document.status

        assignment.status = SignerAssignment.STATUS_REJECTED
        assignment.rejected_at = timezone.now()
        assignment.rejection_reason = reason
        assignment.signed_ip = ip
        assignment.save(
            update_fields=["status", "rejected_at", "rejection_reason", "signed_ip"]
        )

        document.status = SignableDocument.STATUS_REJECTED
        document.save(update_fields=["status"])

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_REJECT,
            request=request,
            actor=assignment.user,
            detail=f"{assignment.display_name} rejected. Reason: {reason}",
            assignment=assignment,
            status_before=old_status,
            status_after=SignableDocument.STATUS_REJECTED,
        )

        from .tasks import send_rejection_notification

        send_rejection_notification.delay(str(assignment.pk))

        return Response(
            {
                "status": "rejected",
                "document_status": document.status,
                "message": "Document rejected.",
            }
        )

    def _resolve_signature(self, request, assignment, vd) -> CapturedSignature | None:
        saved_id = vd.get("saved_signature_id")
        if saved_id:
            try:
                user = assignment.user or (
                    request.user if request.user.is_authenticated else None
                )
                return CapturedSignature.objects.get(pk=saved_id, user=user)
            except CapturedSignature.DoesNotExist:
                return None

        data_uri = vd.get("signature_data_uri", "")
        typed_text = vd.get("typed_text", "")

        if data_uri:
            import base64

            from django.core.files.base import ContentFile

            try:
                header, encoded = data_uri.split(",", 1)
                raw_bytes = base64.b64decode(encoded)
                ext = ".png" if "png" in header else ".jpg"
                sig = CapturedSignature(
                    user=assignment.user if assignment.user else None,
                    source=vd.get("signature_source", CapturedSignature.SOURCE_DRAWN),
                    image_data_uri=data_uri,
                )
                sig.image.save(f"sig{ext}", ContentFile(raw_bytes), save=False)
                sig.save()
                return sig
            except Exception as exc:
                logger.error("Signature save failed: %s", exc)
                return None

        if typed_text:
            from django.core.files.base import ContentFile

            try:
                sig_bytes = _render_typed_signature(typed_text)
                sig = CapturedSignature(
                    user=assignment.user if assignment.user else None,
                    source=CapturedSignature.SOURCE_TYPED,
                    typed_text=typed_text,
                    typed_font=vd.get("typed_font", "Dancing Script"),
                )
                import base64

                sig.image_data_uri = (
                    "data:image/png;base64," + base64.b64encode(sig_bytes).decode()
                )
                sig.image.save("typed_sig.png", ContentFile(sig_bytes), save=False)
                sig.save()
                return sig
            except Exception as exc:
                logger.error("Typed signature render failed: %s", exc)
                return None

        return None


class OTPRequestAPIView(APIView):
    """
    POST /api/esignature/sign/<token>/otp/request/
    Issues a fresh OTP and dispatches the email.
    """

    permission_classes = []

    def post(self, request, token):
        assignment = get_object_or_404(
            SignerAssignment.objects.select_related("document"),
            signing_token=token,
        )

        if not assignment.token_is_valid:
            return Response(
                {"detail": "Invalid or expired signing token."},
                status=status.HTTP_410_GONE,
            )

        otp_record = _issue_signing_otp(assignment)

        from .tasks import send_otp_email

        send_otp_email.delay(str(otp_record.pk))

        _record_audit(
            document=assignment.document,
            action=ESignatureAuditLog.ACTION_OTP_REQUEST,
            request=request,
            detail=f"OTP requested for {assignment.display_email}",
            assignment=assignment,
        )

        return Response(
            {
                "detail": f"Verification code sent to {assignment.display_email}.",
                "expires_in_minutes": 10,
            }
        )


class OTPVerifyAPIView(APIView):
    """
    POST /api/esignature/sign/<token>/otp/verify/
    Verifies the OTP code entered by the signer.
    """

    permission_classes = []

    def post(self, request, token):
        assignment = get_object_or_404(
            SignerAssignment.objects.select_related("document"),
            signing_token=token,
        )

        if not assignment.token_is_valid:
            return Response(
                {"detail": "Invalid or expired signing token."},
                status=status.HTTP_410_GONE,
            )

        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data["code"]

        otp_record = (
            SigningOTPRecord.objects.filter(
                assignment=assignment,
                used=False,
            )
            .order_by("-issued_at")
            .first()
        )

        if not otp_record or not otp_record.is_valid:
            return Response(
                {"detail": "Verification code has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_record.code != code:
            _record_audit(
                document=assignment.document,
                action=ESignatureAuditLog.ACTION_OTP_REQUEST,
                request=request,
                detail=f"Failed OTP attempt for {assignment.display_email}",
                assignment=assignment,
            )
            return Response(
                {"detail": "Invalid verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Consume the OTP
        otp_record.used = True
        otp_record.used_at = timezone.now()
        otp_record.save(update_fields=["used", "used_at"])

        assignment.otp_verified = True
        assignment.otp_verified_at = timezone.now()
        assignment.status = SignerAssignment.STATUS_OTP_VERIFIED
        assignment.save(update_fields=["otp_verified", "otp_verified_at", "status"])

        _record_audit(
            document=assignment.document,
            action=ESignatureAuditLog.ACTION_OTP_VERIFY,
            request=request,
            detail=f"OTP verified for {assignment.display_email}",
            assignment=assignment,
        )

        return Response(
            {
                "detail": "Identity verified. You may now sign the document.",
                "verified": True,
            }
        )


class DocumentDownloadAPIView(APIView):
    """
    GET /api/esignature/documents/<pk>/download/?type=signed|original

    Serves the PDF file with access control.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        document = get_object_or_404(SignableDocument, pk=pk)
        dl_type = request.query_params.get("type", "signed")

        # Access control
        if not _can_view_document(request.user, document):
            return Response(
                {"detail": "You do not have access to this document."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if dl_type == "original":
            if not _can_manage_document(request.user, document):
                return Response(
                    {
                        "detail": "Only document managers can download the original file."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            file_field = document.original_file
        else:
            # Signed file: only available once fully signed
            if document.status != SignableDocument.STATUS_FULLY_SIGNED:
                return Response(
                    {"detail": "The signed document is not yet available."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # Check download permission
            can_dl = _can_manage_document(request.user, document)
            if not can_dl:
                if document.signers.filter(user=request.user).exists():
                    can_dl = True
                elif document.viewers.filter(
                    user=request.user, can_download=True
                ).exists():
                    can_dl = True
            if not can_dl:
                return Response(
                    {
                        "detail": "You do not have download permission for this document."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            file_field = document.signed_file

        if not file_field:
            return Response(
                {"detail": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Record download in audit log
        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_DOWNLOAD,
            request=request,
            detail=f"{dl_type.capitalize()} file downloaded by {request.user.email}",
        )

        # Integrity check for original
        if dl_type == "original" and document.original_hash:
            if not document.verify_original_integrity():
                _record_audit(
                    document=document,
                    action=ESignatureAuditLog.ACTION_TAMPER_DETECTED,
                    request=request,
                    detail="Tampering detected during download integrity check",
                )
                logger.critical(
                    "INTEGRITY FAILURE: Document %s hash mismatch on download",
                    document.reference_number,
                )

        try:
            file_field.open("rb")
            response = FileResponse(
                file_field,
                content_type="application/pdf",
                as_attachment=True,
                filename=os.path.basename(file_field.name),
            )
            return response
        except Exception as exc:
            logger.error("File serve failed for %s: %s", document.pk, exc)
            return Response(
                {"detail": "File could not be retrieved."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuditLogAPIView(generics.ListAPIView):
    """
    GET /api/esignature/documents/<pk>/audit/
    Paginated audit trail for a specific document.
    """

    serializer_class = ESignatureAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewAuditLogs]

    def get_queryset(self):
        document = get_object_or_404(SignableDocument, pk=self.kwargs["pk"])
        # Extra check: uploaders can view their own document's audit trail
        if not (
            self.request.user.role in CanViewAuditLogs.ALLOWED_ROLES
            or self.request.user == document.uploaded_by
        ):
            raise PermissionDenied
        return document.audit_logs.select_related(
            "actor", "related_assignment"
        ).order_by("-timestamp")


class GlobalAuditLogAPIView(generics.ListAPIView):
    """
    GET /api/esignature/audit/
    Global audit trail across all documents (admin / audit roles only).
    """

    serializer_class = ESignatureAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewAuditLogs]

    def get_queryset(self):
        qs = ESignatureAuditLog.objects.select_related(
            "document", "actor", "related_assignment"
        ).order_by("-timestamp")

        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)

        doc_filter = self.request.query_params.get("document")
        if doc_filter:
            qs = qs.filter(document__pk=doc_filter)

        actor_filter = self.request.query_params.get("actor")
        if actor_filter:
            qs = qs.filter(actor__pk=actor_filter)

        return qs


class SignerRevokeAPIView(APIView):
    """
    DELETE /api/esignature/assignments/<pk>/revoke/
    Revoke (remove) a signer assignment before they have signed.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        assignment = get_object_or_404(
            SignerAssignment.objects.select_related("document"),
            pk=pk,
        )
        document = assignment.document

        if not _can_manage_document(request.user, document):
            return Response(
                {"detail": "You do not have permission to revoke signers."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if assignment.status == SignerAssignment.STATUS_SIGNED:
            return Response(
                {"detail": "Cannot revoke a signer who has already signed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = assignment.display_name
        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_REVOKE,
            request=request,
            detail=f"Signer revoked: {name} (order {assignment.signing_order})",
            assignment=assignment,
        )

        assignment.delete()

        return Response(
            {"detail": f"Signer '{name}' has been removed from this document."},
            status=status.HTTP_200_OK,
        )


class DocumentStatusAPIView(APIView):
    """
    POST /api/esignature/documents/<pk>/status/
    Cancel or reopen a document.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(SignableDocument, pk=pk)

        if not _can_manage_document(request.user, document):
            return Response(
                {
                    "detail": "You do not have permission to change this document's status."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DocumentStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        old_status = document.status

        if action == DocumentStatusSerializer.ACTION_CANCEL:
            if document.status == SignableDocument.STATUS_FULLY_SIGNED:
                return Response(
                    {"detail": "A fully signed document cannot be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            document.status = SignableDocument.STATUS_CANCELLED
            detail = f"Document cancelled by {request.user.email}. Reason: {reason}"

        elif action == DocumentStatusSerializer.ACTION_REOPEN:
            if document.status not in (
                SignableDocument.STATUS_CANCELLED,
                SignableDocument.STATUS_REJECTED,
            ):
                return Response(
                    {"detail": "Only cancelled or rejected documents can be reopened."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            document.status = SignableDocument.STATUS_PENDING
            detail = f"Document reopened by {request.user.email}. Reason: {reason}"

        document.save(update_fields=["status"])

        _record_audit(
            document=document,
            action=ESignatureAuditLog.ACTION_CANCEL,
            request=request,
            detail=detail,
            status_before=old_status,
            status_after=document.status,
        )

        return Response(
            {
                "detail": detail,
                "new_status": document.status,
            }
        )


class SavedSignatureListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/esignature/my-signatures/   — list the user's saved signatures
    POST /api/esignature/my-signatures/   — save a new signature
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CapturedSignatureCreateSerializer
        return CapturedSignatureSerializer

    def get_queryset(self):
        return CapturedSignature.objects.filter(user=self.request.user).order_by(
            "-is_default", "-created_at"
        )


class SavedSignatureDeleteAPIView(generics.DestroyAPIView):
    """
    DELETE /api/esignature/my-signatures/<pk>/
    Delete one of the user's saved signatures.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CapturedSignature.objects.filter(user=self.request.user)


# ============================================================================
# ─── HTMX partial views ─────────────────────────────────────────────────────
# ============================================================================


@login_required
def signing_status_partial(request, pk):
    """
    HTMX endpoint: /esignature/<pk>/status-partial/
    Returns a small HTML fragment with the current signing progress bar.
    Used to poll for live status updates on the document detail page.
    """
    document = get_object_or_404(SignableDocument, pk=pk)
    if not _can_view_document(request.user, document):
        return HttpResponseForbidden()

    return render(
        request,
        "esignature/partials/signing_progress.html",
        {"document": document},
    )


@login_required
def signer_list_partial(request, pk):
    """
    HTMX endpoint: /esignature/<pk>/signers-partial/
    Returns the signer table HTML fragment.
    """
    document = get_object_or_404(SignableDocument, pk=pk)
    if not _can_view_document(request.user, document):
        return HttpResponseForbidden()

    return render(
        request,
        "esignature/partials/signer_list.html",
        {
            "document": document,
            "can_manage": _can_manage_document(request.user, document),
        },
    )


@login_required
def send_reminder_view(request, assignment_pk):
    """
    POST /esignature/assignments/<assignment_pk>/remind/
    Manually trigger a reminder email to a pending signer.
    """
    if request.method != "POST":
        return HttpResponseForbidden()

    assignment = get_object_or_404(
        SignerAssignment.objects.select_related("document"),
        pk=assignment_pk,
    )

    if not _can_manage_document(request.user, assignment.document):
        messages.error(request, "Permission denied.")
        return redirect("esignature:document_detail", pk=assignment.document.pk)

    from .tasks import send_signing_reminder

    send_signing_reminder.delay(str(assignment.pk))

    messages.success(
        request,
        f"Reminder sent to {assignment.display_name}.",
    )
    return redirect("esignature:document_detail", pk=assignment.document.pk)


# ============================================================================
# ─── Internal helpers ───────────────────────────────────────────────────────
# ============================================================================


def _check_and_advance_document(document: SignableDocument):
    """
    After a signing event, check if all required signers have signed and
    advance the document status accordingly.  Triggers the Celery
    finalisation task when the document is complete.
    """
    document.refresh_from_db()

    required_signers = document.signers.filter(is_required=True)
    total_required = required_signers.count()
    signed_required = required_signers.filter(
        status=SignerAssignment.STATUS_SIGNED
    ).count()

    all_signed = total_required > 0 and signed_required == total_required

    if all_signed:
        old_status = document.status
        document.status = SignableDocument.STATUS_FULLY_SIGNED
        document.finalised_at = timezone.now()
        document.save(update_fields=["status", "finalised_at"])

        # Kick off the PDF finalisation task
        from .tasks import finalise_signed_document

        finalise_signed_document.delay(str(document.pk))
    elif document.status == SignableDocument.STATUS_PENDING:
        document.status = SignableDocument.STATUS_IN_PROGRESS
        document.save(update_fields=["status"])


def _render_typed_signature(text: str) -> bytes:
    """
    Render a typed signature as a PNG image using ReportLab.
    Returns PNG bytes.
    """
    import io as _io

    from reportlab.lib.pagesizes import landscape
    from reportlab.pdfgen import canvas as rl_canvas

    W, H = 400, 100
    buf = _io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    c.setFillColorRGB(0.1, 0.04, 0.24)  # brand primary
    c.setFont("Helvetica-Oblique", 36)
    c.drawCentredString(W / 2, H / 2 - 12, text[:30])
    c.save()
    buf.seek(0)

    # Convert PDF bytes to PNG via Pillow if possible
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(buf.read(), dpi=150, first_page=1, last_page=1)
        if images:
            out = _io.BytesIO()
            images[0].save(out, format="PNG")
            return out.getvalue()
    except Exception:
        pass

    # Fallback: just return the raw bytes (won't be a PNG, but won't crash)
    buf.seek(0)
    return buf.read()
