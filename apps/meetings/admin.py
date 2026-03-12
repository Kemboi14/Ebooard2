from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AgendaItem,
    Meeting,
    MeetingAction,
    MeetingAttendance,
    MeetingMinutes,
    VideoConferenceParticipant,
    VideoConferenceRecording,
    VideoConferenceSession,
)


class AgendaItemInline(admin.TabularInline):
    model = AgendaItem
    extra = 0
    fields = (
        "order",
        "title",
        "item_type",
        "presenter",
        "estimated_duration",
        "is_discussed",
    )
    ordering = ("order",)


class MeetingAttendanceInline(admin.TabularInline):
    model = MeetingAttendance
    extra = 0
    fields = ("attendee", "status", "rsvp_status", "check_in_time", "check_out_time")


class MeetingActionInline(admin.TabularInline):
    model = MeetingAction
    extra = 0
    fields = ("title", "assigned_to", "action_due_date", "status", "priority")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "meeting_type",
        "status_badge",
        "scheduled_date",
        "organizer",
        "is_virtual",
        "attendee_count",
        "created_at",
    )
    list_filter = (
        "status",
        "meeting_type",
        "is_virtual",
        "virtual_platform",
        "scheduled_date",
    )
    search_fields = ("title", "description", "reference_number", "organizer__email")
    readonly_fields = ("id", "created_at", "updated_at", "invitations_sent_at")
    date_hierarchy = "scheduled_date"
    ordering = ("-scheduled_date",)
    inlines = [AgendaItemInline, MeetingAttendanceInline, MeetingActionInline]

    fieldsets = (
        (
            "Core Details",
            {
                "fields": (
                    "id",
                    "title",
                    "description",
                    "meeting_type",
                    "status",
                    "reference_number",
                    "branch",
                    "committee",
                ),
            },
        ),
        (
            "Scheduling",
            {
                "fields": (
                    "scheduled_date",
                    "scheduled_end_time",
                    "location",
                    "venue_notes",
                    "timezone_display",
                ),
            },
        ),
        (
            "Virtual Meeting",
            {
                "fields": (
                    "is_virtual",
                    "virtual_platform",
                    "virtual_meeting_url",
                    "virtual_meeting_id",
                    "virtual_meeting_password",
                    "virtual_dial_in",
                    "virtual_host_key",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Video Conference Settings",
            {
                "fields": (
                    "enable_recording",
                    "enable_chat",
                    "enable_screen_sharing",
                    "enable_breakout_rooms",
                    "enable_waiting_room",
                    "max_participants",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Quorum",
            {
                "fields": ("quorum_required", "quorum_status"),
            },
        ),
        (
            "Participants",
            {
                "fields": ("organizer", "attendees", "required_attendees"),
            },
        ),
        (
            "Post-Meeting",
            {
                "fields": (
                    "recording_url",
                    "recording_duration",
                    "agenda",
                    "platform_data",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Notifications",
            {
                "fields": (
                    "reminder_sent_24h",
                    "reminder_sent_1h",
                    "invitations_sent_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
            },
        ),
    )

    filter_horizontal = ("attendees", "required_attendees")

    def status_badge(self, obj):
        colors = {
            "scheduled": "#3b82f6",
            "in_progress": "#f59e0b",
            "completed": "#10b981",
            "cancelled": "#ef4444",
            "postponed": "#8b5cf6",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def attendee_count(self, obj):
        return obj.attendees.count()

    attendee_count.short_description = "Attendees"


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "meeting",
        "item_type",
        "order",
        "presenter",
        "estimated_duration",
        "is_discussed",
    )
    list_filter = ("item_type", "is_discussed", "meeting__status")
    search_fields = ("title", "description", "meeting__title")
    ordering = ("meeting", "order")
    raw_id_fields = ("meeting",)


@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "status",
        "drafted_by",
        "drafted_at",
        "approved_by",
        "approved_at",
    )
    list_filter = ("status",)
    search_fields = ("meeting__title", "content")
    readonly_fields = (
        "drafted_at",
        "submitted_at",
        "reviewed_at",
        "approved_at",
        "published_at",
        "updated_at",
    )
    raw_id_fields = ("meeting",)

    fieldsets = (
        (
            "Minutes",
            {
                "fields": ("meeting", "status", "content", "decisions", "action_items"),
            },
        ),
        (
            "Attachments",
            {
                "fields": ("attachment", "next_meeting_date"),
            },
        ),
        (
            "Workflow",
            {
                "fields": (
                    "drafted_by",
                    "drafted_at",
                    "reviewed_by",
                    "reviewed_at",
                    "approved_by",
                    "approved_at",
                    "published_by",
                    "published_at",
                    "submitted_at",
                    "updated_at",
                ),
            },
        ),
    )


@admin.register(MeetingAttendance)
class MeetingAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "attendee",
        "status",
        "rsvp_status",
        "check_in_time",
        "check_out_time",
    )
    list_filter = ("status", "rsvp_status")
    search_fields = (
        "meeting__title",
        "attendee__email",
        "attendee__first_name",
        "attendee__last_name",
    )
    raw_id_fields = ("meeting", "attendee", "recorded_by")


@admin.register(MeetingAction)
class MeetingActionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "meeting",
        "assigned_to",
        "status",
        "priority",
        "due_date",
        "is_overdue",
    )
    list_filter = ("status", "priority")
    search_fields = ("title", "description", "meeting__title", "assigned_to__email")
    raw_id_fields = ("meeting", "agenda_item", "assigned_to", "created_by")

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True
    is_overdue.short_description = "Overdue?"


@admin.register(VideoConferenceSession)
class VideoConferenceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "meeting",
        "platform",
        "status",
        "started_at",
        "ended_at",
        "participant_count",
    )
    list_filter = ("platform", "status")
    search_fields = ("meeting__title", "session_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(VideoConferenceParticipant)
class VideoConferenceParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "email",
        "session",
        "role",
        "joined_at",
        "left_at",
        "attended",
    )
    list_filter = ("role", "attended")
    search_fields = ("display_name", "email", "session__meeting__title")
    raw_id_fields = ("session", "user")


@admin.register(VideoConferenceRecording)
class VideoConferenceRecordingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "meeting",
        "status",
        "format",
        "is_public",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "format", "is_public")
    search_fields = ("title", "meeting__title")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("meeting", "session")
