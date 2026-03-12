from django.urls import path

from . import views

app_name = "esignature"

urlpatterns = [
    # -----------------------------------------------------------------------
    # Template Views
    # -----------------------------------------------------------------------
    path(
        "",
        views.DocumentListView.as_view(),
        name="document_list",
    ),
    path(
        "upload/",
        views.DocumentUploadView.as_view(),
        name="document_upload",
    ),
    path(
        "<uuid:pk>/",
        views.DocumentDetailView.as_view(),
        name="document_detail",
    ),
    path(
        "<uuid:pk>/audit/",
        views.AuditTrailView.as_view(),
        name="audit_trail",
    ),
    path(
        "my-signatures/",
        views.MySignaturesView.as_view(),
        name="my_signatures",
    ),
    # Public signing interface (token-gated, no login required)
    path(
        "sign/<uuid:token>/",
        views.SigningInterfaceView.as_view(),
        name="sign_document",
    ),
    # -----------------------------------------------------------------------
    # HTMX Partials
    # -----------------------------------------------------------------------
    path(
        "<uuid:pk>/status-partial/",
        views.signing_status_partial,
        name="signing_status_partial",
    ),
    path(
        "<uuid:pk>/signers-partial/",
        views.signer_list_partial,
        name="signer_list_partial",
    ),
    path(
        "assignments/<uuid:assignment_pk>/remind/",
        views.send_reminder_view,
        name="send_reminder",
    ),
    # -----------------------------------------------------------------------
    # REST API Endpoints
    # -----------------------------------------------------------------------
    # Documents
    path(
        "api/documents/",
        views.DocumentListCreateAPIView.as_view(),
        name="api_document_list",
    ),
    path(
        "api/documents/<uuid:pk>/",
        views.DocumentRetrieveUpdateAPIView.as_view(),
        name="api_document_detail",
    ),
    path(
        "api/documents/<uuid:pk>/invite/",
        views.InviteSignerAPIView.as_view(),
        name="api_invite_signer",
    ),
    path(
        "api/documents/<uuid:pk>/download/",
        views.DocumentDownloadAPIView.as_view(),
        name="api_document_download",
    ),
    path(
        "api/documents/<uuid:pk>/audit/",
        views.AuditLogAPIView.as_view(),
        name="api_document_audit",
    ),
    path(
        "api/documents/<uuid:pk>/status/",
        views.DocumentStatusAPIView.as_view(),
        name="api_document_status",
    ),
    # Signing flow
    path(
        "api/sign/<uuid:token>/",
        views.SigningAPIView.as_view(),
        name="api_sign_document",
    ),
    path(
        "api/sign/<uuid:token>/otp/request/",
        views.OTPRequestAPIView.as_view(),
        name="api_otp_request",
    ),
    path(
        "api/sign/<uuid:token>/otp/verify/",
        views.OTPVerifyAPIView.as_view(),
        name="api_otp_verify",
    ),
    # Signer assignments
    path(
        "api/assignments/<uuid:pk>/revoke/",
        views.SignerRevokeAPIView.as_view(),
        name="api_revoke_signer",
    ),
    # Saved signatures
    path(
        "api/my-signatures/",
        views.SavedSignatureListCreateAPIView.as_view(),
        name="api_my_signatures",
    ),
    path(
        "api/my-signatures/<uuid:pk>/",
        views.SavedSignatureDeleteAPIView.as_view(),
        name="api_delete_signature",
    ),
    # Global audit log (admin / audit roles)
    path(
        "api/audit/",
        views.GlobalAuditLogAPIView.as_view(),
        name="api_global_audit",
    ),
]
