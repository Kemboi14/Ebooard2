"""
apps/esignature/tasks.py
────────────────────────
Celery tasks for the e-signature module.

Tasks
-----
send_signing_invitation        — Email a signer their secure signing link.
send_signing_reminder          — Reminder email to a pending signer.
send_fully_signed_notification — Notify uploader + all signers the doc is done.
send_rejection_notification    — Notify uploader when a signer rejects.
finalise_signed_document       — Embed all signatures into the PDF, save result.
expire_overdue_documents       — Periodic: mark expired documents / assignments.
send_otp_email                 — Deliver a one-time signing OTP to the signer.
"""

from __future__ import annotations

import io
import logging
import random
import string
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger("esignature.tasks")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_assignment(assignment_pk: str):
    """Lazy import to avoid circular imports at module load time."""
    from apps.esignature.models import SignerAssignment

    try:
        return SignerAssignment.objects.select_related(
            "document", "user", "document__uploaded_by"
        ).get(pk=assignment_pk)
    except SignerAssignment.DoesNotExist:
        logger.error("SignerAssignment %s not found.", assignment_pk)
        return None


def _get_document(document_pk: str):
    from apps.esignature.models import SignableDocument

    try:
        return SignableDocument.objects.select_related("uploaded_by", "branch").get(
            pk=document_pk
        )
    except SignableDocument.DoesNotExist:
        logger.error("SignableDocument %s not found.", document_pk)
        return None


def _build_absolute_url(path: str) -> str:
    """Construct a full URL using SITE_URL from settings or a sensible default."""
    base = getattr(settings, "SITE_URL", "https://eboard.enwealth.co.ke").rstrip("/")
    return f"{base}{path}"


def _send_email(
    subject: str,
    to: list[str],
    text_body: str,
    html_body: str,
    reply_to: list[str] | None = None,
) -> bool:
    """
    Send a multi-part (text + HTML) email.
    Returns True on success, False on failure.
    """
    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL", "Enwealth E-Board <noreply@enwealth.co.ke>"
    )
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=to,
            reply_to=reply_to or [],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.error("Email send failed to %s: %s", to, exc)
        return False


def _log_audit(document, action: str, actor=None, detail: str = "", assignment=None):
    """Fire-and-forget audit log entry."""
    from apps.esignature.models import ESignatureAuditLog

    try:
        ESignatureAuditLog.record(
            document=document,
            action=action,
            actor=actor,
            detail=detail,
            related_assignment=assignment,
        )
    except Exception as exc:
        logger.warning("Audit log failed: %s", exc)


# ---------------------------------------------------------------------------
# Task: Send signing invitation
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="esignature.send_signing_invitation",
)
def send_signing_invitation(self, assignment_pk: str) -> dict:
    """
    Send a secure, token-based signing link to the assigned signer.

    The signing token is embedded in the URL and is valid until the document
    expires or the assignment is revoked.
    """
    assignment = _get_assignment(assignment_pk)
    if assignment is None:
        return {"status": "error", "reason": "assignment_not_found"}

    document = assignment.document

    # Build the absolute signing URL
    signing_path = reverse(
        "esignature:sign_document",
        kwargs={"token": assignment.signing_token},
    )
    signing_url = _build_absolute_url(signing_path)

    # Build the document detail URL for the uploader
    detail_path = reverse("esignature:document_detail", kwargs={"pk": document.pk})
    detail_url = _build_absolute_url(detail_path)

    # Template context
    ctx = {
        "signer_name": assignment.display_name,
        "signer_email": assignment.display_email,
        "document_title": document.title,
        "document_reference": document.reference_number,
        "uploaded_by_name": document.uploaded_by.get_full_name(),
        "uploaded_by_email": document.uploaded_by.email,
        "signing_url": signing_url,
        "detail_url": detail_url,
        "expires_at": document.expires_at,
        "require_otp": document.require_otp,
        "signing_order": assignment.signing_order,
        "total_signers": document.total_signers,
        "role_display": assignment.get_role_display(),
        "platform_name": "Enwealth E-Board",
    }

    subject = (
        f"Action Required: Please sign '{document.title}' [{document.reference_number}]"
    )
    text_body = render_to_string("esignature/email/signing_invitation.txt", ctx)
    html_body = render_to_string("esignature/email/signing_invitation.html", ctx)

    to_email = assignment.display_email
    if not to_email:
        logger.error("Assignment %s has no email address.", assignment_pk)
        return {"status": "error", "reason": "no_email"}

    success = _send_email(
        subject=subject,
        to=[to_email],
        text_body=text_body,
        html_body=html_body,
        reply_to=[document.uploaded_by.email],
    )

    if success:
        # Update assignment state
        assignment.status = assignment.STATUS_NOTIFIED
        assignment.notified_at = timezone.now()
        assignment.save(update_fields=["status", "notified_at"])

        _log_audit(
            document=document,
            action=ESignatureAuditLogAction.INVITE,
            detail=f"Signing invitation sent to {to_email}",
            assignment=assignment,
        )
        logger.info(
            "Signing invitation sent to %s for document %s",
            to_email,
            document.reference_number,
        )
        return {"status": "sent", "to": to_email}
    else:
        try:
            raise self.retry(exc=Exception("Email send failed"), countdown=120)
        except self.MaxRetriesExceededError:
            return {"status": "failed", "to": to_email}


# ---------------------------------------------------------------------------
# Task: Send signing reminder
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    name="esignature.send_signing_reminder",
)
def send_signing_reminder(self, assignment_pk: str) -> dict:
    """
    Send a polite reminder to a signer who has not yet signed.
    """
    from apps.esignature.models import SignerAssignment

    assignment = _get_assignment(assignment_pk)
    if assignment is None:
        return {"status": "error", "reason": "assignment_not_found"}

    if assignment.status in (
        SignerAssignment.STATUS_SIGNED,
        SignerAssignment.STATUS_REJECTED,
        SignerAssignment.STATUS_EXPIRED,
    ):
        return {"status": "skipped", "reason": f"already_{assignment.status}"}

    document = assignment.document

    signing_path = reverse(
        "esignature:sign_document",
        kwargs={"token": assignment.signing_token},
    )
    signing_url = _build_absolute_url(signing_path)

    days_since_invite = (
        (timezone.now() - assignment.notified_at).days if assignment.notified_at else 0
    )

    ctx = {
        "signer_name": assignment.display_name,
        "document_title": document.title,
        "document_reference": document.reference_number,
        "signing_url": signing_url,
        "days_since_invite": days_since_invite,
        "expires_at": document.expires_at,
        "reminder_count": assignment.reminder_count + 1,
        "platform_name": "Enwealth E-Board",
    }

    subject = (
        f"Reminder: Your signature is required on '{document.title}' "
        f"[{document.reference_number}]"
    )
    text_body = render_to_string("esignature/email/signing_reminder.txt", ctx)
    html_body = render_to_string("esignature/email/signing_reminder.html", ctx)

    success = _send_email(
        subject=subject,
        to=[assignment.display_email],
        text_body=text_body,
        html_body=html_body,
    )

    if success:
        assignment.reminder_sent_at = timezone.now()
        assignment.reminder_count += 1
        assignment.save(update_fields=["reminder_sent_at", "reminder_count"])

        _log_audit(
            document=document,
            action=ESignatureAuditLogAction.REMIND,
            detail=f"Reminder #{assignment.reminder_count} sent to {assignment.display_email}",
            assignment=assignment,
        )
        return {"status": "sent", "reminder_count": assignment.reminder_count}
    else:
        try:
            raise self.retry(exc=Exception("Email send failed"))
        except self.MaxRetriesExceededError:
            return {"status": "failed"}


# ---------------------------------------------------------------------------
# Task: Fully signed notification
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="esignature.send_fully_signed_notification",
)
def send_fully_signed_notification(self, document_pk: str) -> dict:
    """
    Notify the document owner and all signers that the document has been
    fully signed and is ready for download.
    """
    document = _get_document(document_pk)
    if document is None:
        return {"status": "error", "reason": "document_not_found"}

    detail_path = reverse("esignature:document_detail", kwargs={"pk": document.pk})
    detail_url = _build_absolute_url(detail_path)

    signers_info = [
        {
            "name": s.display_name,
            "email": s.display_email,
            "role": s.get_role_display(),
            "signed_at": s.signed_at,
        }
        for s in document.signers.filter(
            status__in=["signed", "otp_verified"]
        ).order_by("signing_order")
    ]

    ctx = {
        "document_title": document.title,
        "document_reference": document.reference_number,
        "detail_url": detail_url,
        "signers": signers_info,
        "finalised_at": document.finalised_at or timezone.now(),
        "platform_name": "Enwealth E-Board",
    }

    # Collect all recipients: uploader + all signers with emails
    recipients = {document.uploaded_by.email}
    for s in document.signers.all():
        email = s.display_email
        if email:
            recipients.add(email)

    subject = f"Document Fully Signed: '{document.title}' [{document.reference_number}]"

    sent_count = 0
    for email in recipients:
        ctx["recipient_email"] = email
        # Personalise greeting if we have a matching signer
        ctx["recipient_name"] = _name_for_email(document, email)

        text_body = render_to_string("esignature/email/fully_signed.txt", ctx)
        html_body = render_to_string("esignature/email/fully_signed.html", ctx)

        if _send_email(
            subject=subject, to=[email], text_body=text_body, html_body=html_body
        ):
            sent_count += 1

    logger.info(
        "Fully-signed notification sent to %d recipients for %s",
        sent_count,
        document.reference_number,
    )
    return {"status": "sent", "recipients": sent_count}


# ---------------------------------------------------------------------------
# Task: Rejection notification
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="esignature.send_rejection_notification",
)
def send_rejection_notification(self, assignment_pk: str) -> dict:
    """
    Notify the document uploader (and optionally other signers) when
    a signer rejects the document.
    """
    assignment = _get_assignment(assignment_pk)
    if assignment is None:
        return {"status": "error", "reason": "assignment_not_found"}

    document = assignment.document
    detail_path = reverse("esignature:document_detail", kwargs={"pk": document.pk})
    detail_url = _build_absolute_url(detail_path)

    ctx = {
        "rejector_name": assignment.display_name,
        "rejector_email": assignment.display_email,
        "rejection_reason": assignment.rejection_reason,
        "document_title": document.title,
        "document_reference": document.reference_number,
        "detail_url": detail_url,
        "rejected_at": assignment.rejected_at or timezone.now(),
        "platform_name": "Enwealth E-Board",
    }

    subject = f"Signature Rejected: '{document.title}' [{document.reference_number}]"

    # Notify the uploader
    text_body = render_to_string("esignature/email/rejection_notification.txt", ctx)
    html_body = render_to_string("esignature/email/rejection_notification.html", ctx)

    _send_email(
        subject=subject,
        to=[document.uploaded_by.email],
        text_body=text_body,
        html_body=html_body,
    )

    _log_audit(
        document=document,
        action=ESignatureAuditLogAction.REJECT,
        detail=(
            f"{assignment.display_name} rejected. Reason: {assignment.rejection_reason}"
        ),
        assignment=assignment,
    )

    return {"status": "sent", "to": document.uploaded_by.email}


# ---------------------------------------------------------------------------
# Task: Send signing OTP
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="esignature.send_otp_email",
)
def send_otp_email(self, otp_record_pk: str) -> dict:
    """
    Generate and email a 6-digit OTP to the signer.
    The OTP record is created beforehand in the view; this task sends the email.
    """
    from apps.esignature.models import SigningOTPRecord

    try:
        otp_record = SigningOTPRecord.objects.select_related(
            "assignment__document",
            "assignment__user",
        ).get(pk=otp_record_pk)
    except SigningOTPRecord.DoesNotExist:
        logger.error("SigningOTPRecord %s not found.", otp_record_pk)
        return {"status": "error"}

    assignment = otp_record.assignment
    document = assignment.document

    ctx = {
        "signer_name": assignment.display_name,
        "otp_code": otp_record.code,
        "document_title": document.title,
        "document_reference": document.reference_number,
        "expires_in_minutes": 10,
        "platform_name": "Enwealth E-Board",
    }

    subject = f"Your signing verification code: {otp_record.code}"
    text_body = render_to_string("esignature/email/otp_email.txt", ctx)
    html_body = render_to_string("esignature/email/otp_email.html", ctx)

    success = _send_email(
        subject=subject,
        to=[assignment.display_email],
        text_body=text_body,
        html_body=html_body,
    )

    _log_audit(
        document=document,
        action=ESignatureAuditLogAction.OTP_REQUEST,
        detail=f"OTP sent to {assignment.display_email}",
        assignment=assignment,
    )

    return {"status": "sent" if success else "failed"}


# ---------------------------------------------------------------------------
# Task: Finalise signed document (embed all signatures into PDF)
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="esignature.finalise_signed_document",
    time_limit=120,
    soft_time_limit=100,
)
def finalise_signed_document(self, document_pk: str) -> dict:
    """
    After all required signers have signed:

    1.  Collect all CapturedSignature images and their placements.
    2.  Call PDFSigningService.embed_multiple_signatures() to overlay all
        stamps on the original PDF in signing order.
    3.  Build and append the signing manifest page.
    4.  Compute the SHA-256 of the final file and store it.
    5.  Update the document status to FULLY_SIGNED.
    6.  Trigger send_fully_signed_notification.
    """
    from apps.esignature.models import (
        ESignatureAuditLog,
        SignableDocument,
        SignerAssignment,
    )
    from apps.esignature.pdf_service import (
        PDFSigningError,
        PDFSigningService,
        SignaturePlacement,
        SignatureStampData,
    )

    document = _get_document(document_pk)
    if document is None:
        return {"status": "error", "reason": "not_found"}

    if document.status == SignableDocument.STATUS_FULLY_SIGNED:
        return {"status": "skipped", "reason": "already_finalised"}

    # Gather signed assignments in order
    signed_assignments = list(
        document.signers.filter(status=SignerAssignment.STATUS_SIGNED)
        .prefetch_related("signing_event__signature")
        .order_by("signing_order")
    )

    if not signed_assignments:
        return {"status": "skipped", "reason": "no_signatures"}

    # Build stamp list
    stamps = []
    signer_manifest_rows = []

    for assignment in signed_assignments:
        event = getattr(assignment, "signing_event", None)
        sig_image = None
        if event and event.signature:
            try:
                sig_image = event.signature.image_data_uri or event.signature.image
            except Exception:
                sig_image = None

        placement = SignaturePlacement.from_dict(assignment.placement or {})

        stamp = SignatureStampData(
            signer_name=assignment.display_name,
            signer_email=assignment.display_email,
            signed_at=assignment.signed_at or timezone.now(),
            signing_reference=(
                f"{document.reference_number} · "
                f"Signer {assignment.signing_order} of {document.total_signers}"
            ),
            ip_address=assignment.signed_ip or "",
            placement=placement,
            signature_image=sig_image,
        )
        stamps.append(stamp)

        signer_manifest_rows.append(
            {
                "name": assignment.display_name,
                "email": assignment.display_email,
                "role": assignment.get_role_display(),
                "signed_at": assignment.signed_at,
                "ip_address": assignment.signed_ip or "",
            }
        )

    # Load the original PDF bytes
    try:
        document.original_file.open("rb")
        original_bytes = document.original_file.read()
        document.original_file.close()
    except Exception as exc:
        logger.error("Cannot read original file for %s: %s", document_pk, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "error", "reason": "file_read_failed"}

    # Embed all signatures
    try:
        signed_bytes, signed_hash = PDFSigningService.embed_multiple_signatures(
            source_pdf=original_bytes,
            stamps=stamps,
            expected_hash=document.original_hash,
        )
    except Exception as exc:
        logger.error("PDF signing failed for %s: %s", document_pk, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "error", "reason": str(exc)}

    # Build and append manifest
    try:
        manifest_bytes = PDFSigningService.build_signing_manifest(
            document_title=document.title,
            reference_number=document.reference_number,
            original_hash=document.original_hash,
            signed_hash=signed_hash,
            signers=signer_manifest_rows,
        )
        final_bytes = PDFSigningService.append_manifest(signed_bytes, manifest_bytes)
        final_hash = PDFSigningService.verify_integrity.__func__  # just recompute
        import hashlib

        final_hash = hashlib.sha256(final_bytes).hexdigest()
    except Exception as exc:
        logger.warning(
            "Manifest append failed for %s (using signed-only PDF): %s",
            document_pk,
            exc,
        )
        final_bytes = signed_bytes
        final_hash = signed_hash

    # Save the signed file
    signed_filename = f"signed_{document.reference_number.replace('-', '_')}.pdf"
    document.signed_file.save(signed_filename, ContentFile(final_bytes), save=False)
    document.signed_hash = final_hash
    document.status = SignableDocument.STATUS_FULLY_SIGNED
    document.finalised_at = timezone.now()
    document.save(
        update_fields=["signed_file", "signed_hash", "status", "finalised_at"]
    )

    _log_audit(
        document=document,
        action=ESignatureAuditLogAction.SIGN,
        detail=(
            f"Document fully signed by {len(signed_assignments)} signer(s). "
            f"Final SHA-256: {final_hash[:16]}…"
        ),
    )

    logger.info(
        "Document %s finalised successfully. Hash: %s",
        document.reference_number,
        final_hash[:16],
    )

    # Trigger the fully-signed notification (async)
    send_fully_signed_notification.delay(str(document.pk))

    return {
        "status": "finalised",
        "document": document.reference_number,
        "signed_hash": final_hash,
        "signers": len(signed_assignments),
    }


# ---------------------------------------------------------------------------
# Periodic task: Expire overdue documents
# ---------------------------------------------------------------------------


@shared_task(name="esignature.expire_overdue_documents")
def expire_overdue_documents() -> dict:
    """
    Periodic task (run hourly via Celery Beat).

    Marks documents and signer assignments as EXPIRED when:
    - document.expires_at < now AND status is still draft / pending / in_progress
    - or an individual signer's token_expires_at < now
    """
    from apps.esignature.models import SignableDocument, SignerAssignment

    now = timezone.now()

    # Expire documents
    expired_docs = SignableDocument.objects.filter(
        expires_at__lt=now,
        status__in=[
            SignableDocument.STATUS_DRAFT,
            SignableDocument.STATUS_PENDING,
            SignableDocument.STATUS_IN_PROGRESS,
        ],
    )
    doc_count = expired_docs.count()
    for doc in expired_docs:
        _log_audit(
            document=doc,
            action=ESignatureAuditLogAction.EXPIRE,
            detail="Document expired automatically by scheduled task",
            status_before=doc.status,
            status_after=SignableDocument.STATUS_EXPIRED,
        )
    expired_docs.update(status=SignableDocument.STATUS_EXPIRED)

    # Expire individual assignments whose token has expired
    expired_assignments = SignerAssignment.objects.filter(
        token_expires_at__lt=now,
        status__in=[
            SignerAssignment.STATUS_PENDING,
            SignerAssignment.STATUS_NOTIFIED,
            SignerAssignment.STATUS_VIEWED,
            SignerAssignment.STATUS_OTP_VERIFIED,
        ],
    )
    assign_count = expired_assignments.count()
    expired_assignments.update(status=SignerAssignment.STATUS_EXPIRED)

    logger.info("Expired %d documents and %d assignments.", doc_count, assign_count)

    return {"expired_documents": doc_count, "expired_assignments": assign_count}


# ---------------------------------------------------------------------------
# Periodic task: Send automatic reminders
# ---------------------------------------------------------------------------


@shared_task(name="esignature.send_automatic_reminders")
def send_automatic_reminders() -> dict:
    """
    Periodic task (run daily via Celery Beat).

    For each active signing assignment that:
    - Was notified > 2 days ago
    - Has not yet signed
    - Has fewer than 3 reminders sent

    …send a reminder email.
    """
    from apps.esignature.models import SignerAssignment

    cutoff = timezone.now() - timedelta(days=2)
    pending_assignments = SignerAssignment.objects.filter(
        status__in=[
            SignerAssignment.STATUS_NOTIFIED,
            SignerAssignment.STATUS_VIEWED,
        ],
        notified_at__lt=cutoff,
        reminder_count__lt=3,
        document__status__in=["pending", "in_progress"],
    ).select_related("document")

    queued = 0
    for assignment in pending_assignments:
        send_signing_reminder.delay(str(assignment.pk))
        queued += 1

    logger.info("Queued %d automatic signing reminders.", queued)
    return {"queued_reminders": queued}


# ---------------------------------------------------------------------------
# Helper — look up recipient name for a given email within a document
# ---------------------------------------------------------------------------


def _name_for_email(document, email: str) -> str:
    for signer in document.signers.all():
        if signer.display_email == email:
            return signer.display_name
    if document.uploaded_by.email == email:
        return document.uploaded_by.get_full_name()
    return email


# ---------------------------------------------------------------------------
# String constants for audit actions — imported lazily from models to avoid
# circular imports, but aliased here for convenience.
# ---------------------------------------------------------------------------


class ESignatureAuditLogAction:
    INVITE = "invite"
    REMIND = "remind"
    REJECT = "reject"
    SIGN = "sign"
    OTP_REQUEST = "otp_request"
    OTP_VERIFY = "otp_verify"
    EXPIRE = "expire"
    UPLOAD = "upload"
    VIEW = "view"
    DOWNLOAD = "download"
    CANCEL = "cancel"
