from django.contrib import admin

from .models import AuditLog, AuditLogExport, AuditLogRetention


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "ip_address", "timestamp", "module", "severity")
    list_filter = ("action", "severity", "module", "timestamp")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "ip_address",
        "description",
    )
    readonly_fields = (
        "id",
        "user",
        "action",
        "severity",
        "module",
        "description",
        "details",
        "content_type",
        "object_id",
        "ip_address",
        "user_agent",
        "session_key",
        "request_id",
        "old_values",
        "new_values",
        "metadata",
        "success",
        "error_message",
        "timestamp",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLogExport)
class AuditLogExportAdmin(admin.ModelAdmin):
    list_display = ("user", "requested_at", "record_count", "format", "status")
    list_filter = ("format", "status", "requested_at")
    search_fields = ("user__email",)
    readonly_fields = (
        "user",
        "requested_at",
        "completed_at",
        "record_count",
        "format",
        "filters",
        "file_path",
        "file_size",
        "ip_address",
        "user_agent",
        "error_message",
    )
    ordering = ("-requested_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLogRetention)
class AuditLogRetentionAdmin(admin.ModelAdmin):
    list_display = (
        "module",
        "retention_days",
        "archive_after_days",
        "auto_cleanup",
        "updated_at",
    )
    list_filter = ("auto_cleanup",)
    search_fields = ("module",)
    readonly_fields = ("created_at", "updated_at", "last_cleanup")
