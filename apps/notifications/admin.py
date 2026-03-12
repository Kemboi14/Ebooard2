from django.contrib import admin

from .models import (
    Notification,
    NotificationBatch,
    NotificationChannel,
    NotificationLog,
    NotificationPreference,
    NotificationTemplate,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recipient",
        "notification_type",
        "priority",
        "is_read",
        "is_sent",
        "created_at",
    )
    list_filter = ("notification_type", "priority", "is_read", "is_sent", "created_at")
    search_fields = (
        "title",
        "message",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
    )
    readonly_fields = ("created_at", "read_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("recipient",)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "notification_type", "is_active", "created_at")
    list_filter = ("notification_type", "is_active")
    search_fields = ("name", "subject", "body")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_frequency", "quiet_hours_enabled", "created_at")
    list_filter = ("email_frequency", "quiet_hours_enabled")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user",)


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "channel_type", "is_active", "created_at")
    list_filter = ("channel_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "notification_type",
        "is_sent",
        "total_recipients",
        "sent_count",
        "failed_count",
        "created_at",
    )
    list_filter = ("notification_type", "is_sent", "created_at")
    search_fields = ("title", "message")
    readonly_fields = (
        "created_at",
        "updated_at",
        "sent_count",
        "failed_count",
        "sent_at",
    )
    date_hierarchy = "created_at"
    filter_horizontal = ("recipients",)
    raw_id_fields = ("created_by",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("notification", "channel", "status", "sent_at")
    list_filter = ("status", "channel")
    search_fields = ("notification__title",)
    readonly_fields = ("sent_at",)
    list_select_related = ("notification", "channel")
