import json
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounts.models import User


class Meeting(models.Model):
    """Meeting model for board meetings and governance sessions with enhanced video conferencing"""

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("postponed", "Postponed"),
    ]

    TYPE_CHOICES = [
        ("board", "Board Meeting"),
        ("committee", "Committee Meeting"),
        ("agm", "Annual General Meeting"),
        ("emergency", "Emergency Meeting"),
        ("workshop", "Workshop / Training"),
        ("extraordinary", "Extraordinary General Meeting"),
    ]

    VIDEO_PLATFORM_CHOICES = [
        ("", "No Virtual Meeting"),
        ("zoom", "Zoom"),
        ("teams", "Microsoft Teams"),
        ("google_meet", "Google Meet"),
        ("webex", "Cisco Webex"),
        ("skype", "Skype"),
        ("jitsi", "Jitsi Meet"),
        ("whereby", "Whereby"),
        ("other", "Other Platform"),
    ]

    QUORUM_STATUS_CHOICES = [
        ("not_checked", "Not Checked"),
        ("quorum_met", "Quorum Met"),
        ("quorum_not_met", "Quorum Not Met"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default="board"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    reference_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Official meeting reference / serial number",
    )

    # Organisation context (optional — links to agencies app)
    branch = models.ForeignKey(
        "agencies.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meetings",
        help_text="Branch this meeting belongs to (leave blank for organisation-wide)",
    )
    committee = models.ForeignKey(
        "agencies.Committee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meetings",
        help_text="Committee this meeting is for (optional)",
    )

    # Scheduling
    scheduled_date = models.DateTimeField()
    scheduled_end_time = models.DateTimeField()
    location = models.CharField(
        max_length=300,
        blank=True,
        help_text="Physical location or venue (leave blank for virtual-only)",
    )
    venue_notes = models.TextField(
        blank=True, help_text="Directions, parking, access instructions, etc."
    )
    timezone_display = models.CharField(
        max_length=60,
        blank=True,
        default="Africa/Nairobi",
        help_text="Timezone shown to attendees",
    )

    # Enhanced Video Conferencing
    is_virtual = models.BooleanField(
        default=False, help_text="Enable virtual / hybrid meeting"
    )
    virtual_platform = models.CharField(
        max_length=50,
        choices=VIDEO_PLATFORM_CHOICES,
        default="",
        blank=True,
        help_text="Virtual meeting platform",
    )
    virtual_meeting_url = models.URLField(blank=True, help_text="Virtual meeting link")
    virtual_meeting_id = models.CharField(
        max_length=100, blank=True, help_text="Meeting ID / Room ID"
    )
    virtual_meeting_password = models.CharField(
        max_length=50, blank=True, help_text="Meeting password (if any)"
    )
    virtual_dial_in = models.CharField(
        max_length=100, blank=True, help_text="Dial-in phone number(s)"
    )
    virtual_host_key = models.CharField(
        max_length=50,
        blank=True,
        help_text="Host key (confidential — only shown to organiser)",
    )

    # Video Conferencing Settings
    enable_recording = models.BooleanField(default=False)
    enable_chat = models.BooleanField(default=True)
    enable_screen_sharing = models.BooleanField(default=True)
    enable_breakout_rooms = models.BooleanField(default=False)
    enable_waiting_room = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum participants (leave blank for unlimited)",
    )

    # Agenda (plain-text draft — structured agenda items use AgendaItem model)
    agenda = models.TextField(blank=True, help_text="High-level agenda overview")

    # Quorum
    quorum_required = models.PositiveIntegerField(
        null=True, blank=True, help_text="Minimum attendees required for quorum"
    )
    quorum_status = models.CharField(
        max_length=20, choices=QUORUM_STATUS_CHOICES, default="not_checked"
    )

    # Organizers and attendees
    organizer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="organized_meetings"
    )
    attendees = models.ManyToManyField(
        User, related_name="meeting_attendees", blank=True
    )
    required_attendees = models.ManyToManyField(
        User, related_name="required_meeting_attendees", blank=True
    )

    # Post-meeting
    recording_url = models.URLField(blank=True, help_text="Recording URL after meeting")
    recording_duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Recording duration in minutes"
    )
    platform_data = models.JSONField(default=dict, blank=True)

    # Notifications
    reminder_sent_24h = models.BooleanField(default=False)
    reminder_sent_1h = models.BooleanField(default=False)
    invitations_sent_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_meetings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_date"]
        verbose_name = "Meeting"
        verbose_name_plural = "Meetings"
        indexes = [
            models.Index(fields=["scheduled_date", "status"]),
            models.Index(fields=["virtual_platform"]),
            models.Index(fields=["organizer", "-scheduled_date"]),
            models.Index(fields=["meeting_type", "status"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.scheduled_date.strftime('%b %d, %Y')}"

    def clean(self):
        if self.is_virtual and not self.virtual_platform:
            raise ValidationError(
                "Please select a virtual meeting platform for virtual meetings."
            )
        if self.virtual_platform and not self.virtual_meeting_url:
            raise ValidationError(
                "A virtual meeting URL is required when a platform is selected."
            )
        if self.scheduled_end_time and self.scheduled_end_time <= self.scheduled_date:
            raise ValidationError("End time must be after start time.")

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def is_upcoming(self):
        return self.scheduled_date > timezone.now() and self.status == "scheduled"

    @property
    def is_in_progress(self):
        now = timezone.now()
        return (
            self.scheduled_date <= now <= self.scheduled_end_time
            and self.status == "in_progress"
        )

    @property
    def is_past(self):
        return self.scheduled_end_time < timezone.now()

    @property
    def duration_minutes(self):
        if self.scheduled_end_time:
            delta = self.scheduled_end_time - self.scheduled_date
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def duration_display(self):
        mins = self.duration_minutes
        if mins < 60:
            return f"{mins} min"
        h = mins // 60
        m = mins % 60
        return f"{h}h {m}m" if m else f"{h}h"

    @property
    def has_recording(self):
        return bool(self.recording_url)

    @property
    def platform_display(self):
        return dict(self.VIDEO_PLATFORM_CHOICES).get(self.virtual_platform, "")

    @property
    def attendee_count(self):
        return self.attendees.count()

    @property
    def has_quorum(self):
        if not self.quorum_required:
            return True
        attended = self.attendance_records.filter(status="attended").count()
        return attended >= self.quorum_required

    @property
    def agenda_item_count(self):
        return self.agenda_items.count()

    def get_absolute_url(self):
        return f"/meetings/{self.id}/"

    def generate_meeting_link(self):
        if self.virtual_platform == "zoom" and self.virtual_meeting_id:
            return f"https://zoom.us/j/{self.virtual_meeting_id}"
        return self.virtual_meeting_url

    def get_join_instructions(self):
        instructions = []
        if self.virtual_platform == "zoom":
            instructions.append("Join via Zoom using the link above.")
            if self.virtual_meeting_id:
                instructions.append(f"Meeting ID: {self.virtual_meeting_id}")
            if self.virtual_meeting_password:
                instructions.append(f"Password: {self.virtual_meeting_password}")
            if self.virtual_dial_in:
                instructions.append(f"Dial-in: {self.virtual_dial_in}")
        elif self.virtual_platform == "teams":
            instructions.append("Click the link to join via Microsoft Teams.")
            instructions.append("Ensure you have the Teams app installed.")
        elif self.virtual_platform == "google_meet":
            instructions.append("Click the link to join via Google Meet.")
            instructions.append("Use Google Chrome for the best experience.")
        elif self.virtual_platform == "webex":
            instructions.append("Click the link to join via Cisco Webex.")
        elif self.virtual_platform:
            instructions.append("Click the link above to join the virtual meeting.")
        return instructions

    def can_user_join(self, user):
        return (
            user in self.attendees.all()
            or user in self.required_attendees.all()
            or user == self.organizer
        )


class VideoConferenceSession(models.Model):
    """Track individual video conference sessions"""

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("ended", "Ended"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="video_sessions"
    )
    session_id = models.CharField(
        max_length=200, unique=True, help_text="Platform session ID"
    )
    platform = models.CharField(max_length=50, choices=Meeting.VIDEO_PLATFORM_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    participant_count = models.PositiveIntegerField(default=0)
    peak_participants = models.PositiveIntegerField(default=0)

    recording_started_at = models.DateTimeField(null=True, blank=True)
    recording_ended_at = models.DateTimeField(null=True, blank=True)
    recording_file_size = models.PositiveIntegerField(null=True, blank=True)

    platform_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Conference Session"
        verbose_name_plural = "Video Conference Sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["meeting", "-created_at"]),
            models.Index(fields=["platform", "status"]),
        ]

    def __str__(self):
        return f"{self.meeting.title} — {self.platform} Session"

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def duration_display(self):
        if self.duration_minutes:
            if self.duration_minutes < 60:
                return f"{self.duration_minutes} minutes"
            h = self.duration_minutes // 60
            m = self.duration_minutes % 60
            return f"{h}h {m}m"
        return "N/A"


class VideoConferenceParticipant(models.Model):
    """Track participants in video conference sessions"""

    ROLE_CHOICES = [
        ("host", "Host"),
        ("co_host", "Co-host"),
        ("presenter", "Presenter"),
        ("attendee", "Attendee"),
        ("panelist", "Panelist"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        VideoConferenceSession, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="video_sessions"
    )
    email = models.EmailField()
    display_name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="attendee")

    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    platform_participant_id = models.CharField(max_length=200, blank=True)
    platform_data = models.JSONField(default=dict, blank=True)

    attended = models.BooleanField(default=False)
    was_recording = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Conference Participant"
        verbose_name_plural = "Video Conference Participants"
        ordering = ["joined_at"]
        indexes = [
            models.Index(fields=["session", "-joined_at"]),
            models.Index(fields=["user", "-joined_at"]),
        ]

    def __str__(self):
        return f"{self.display_name} — {self.session.meeting.title}"

    @property
    def attendance_duration(self):
        if self.duration_minutes:
            if self.duration_minutes < 60:
                return f"{self.duration_minutes} min"
            h = self.duration_minutes // 60
            m = self.duration_minutes % 60
            return f"{h}h {m}m"
        return "N/A"


class VideoConferenceRecording(models.Model):
    """Manage video conference recordings"""

    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("available", "Available"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        VideoConferenceSession, on_delete=models.CASCADE, related_name="recordings"
    )
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="recordings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="processing"
    )

    file_url = models.URLField()
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    duration_seconds = models.PositiveIntegerField(help_text="Duration in seconds")
    format = models.CharField(max_length=20, default="mp4")

    is_public = models.BooleanField(default=False)
    access_password = models.CharField(max_length=50, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    platform_recording_id = models.CharField(max_length=200, blank=True)
    platform_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video Conference Recording"
        verbose_name_plural = "Video Conference Recordings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["meeting", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.meeting.title}"

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024**2:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024**3:
            return f"{self.file_size / 1024**2:.1f} MB"
        return f"{self.file_size / 1024**3:.1f} GB"

    @property
    def duration_display(self):
        if self.duration_seconds:
            h = self.duration_seconds // 3600
            m = (self.duration_seconds % 3600) // 60
            s = self.duration_seconds % 60
            if h:
                return f"{h}h {m}m {s}s"
            elif m:
                return f"{m}m {s}s"
            return f"{s}s"
        return "N/A"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def get_absolute_url(self):
        return f"/meetings/recordings/{self.id}/"


class AgendaItem(models.Model):
    """Structured agenda items for meetings"""

    PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    ITEM_TYPE_CHOICES = [
        ("information", "Information"),
        ("discussion", "Discussion"),
        ("decision", "Decision / Resolution"),
        ("action", "Action Item"),
        ("presentation", "Presentation"),
        ("aob", "Any Other Business"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ← fixed: was 'agendaitem_set', now correctly 'agenda_items'
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="agenda_items"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    item_type = models.CharField(
        max_length=20, choices=ITEM_TYPE_CHOICES, default="discussion"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    order = models.PositiveIntegerField(default=0)
    estimated_duration = models.PositiveIntegerField(
        help_text="Estimated duration in minutes", default=15
    )

    attachment = models.FileField(
        upload_to="meetings/agenda_attachments/", blank=True, null=True
    )

    presenter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presented_agenda_items",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_agenda_items"
    )

    is_discussed = models.BooleanField(default=False)
    decision = models.TextField(blank=True, help_text="Decision made on this item")
    action_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_agenda_items",
        help_text="Person responsible for any follow-up action",
    )
    action_due_date = models.DateField(
        null=True, blank=True, help_text="Due date for follow-up action"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Agenda Item"
        verbose_name_plural = "Agenda Items"

    def __str__(self):
        return f"{self.meeting.title} — {self.order}. {self.title}"


class MeetingMinutes(models.Model):
    """Meeting minutes with a formal approval workflow"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted for Review"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("published", "Published"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ← fixed: was using default OneToOne accessor — now explicit related_name='minutes'
    meeting = models.OneToOneField(
        Meeting, on_delete=models.CASCADE, related_name="minutes"
    )
    content = models.TextField(help_text="Full meeting minutes")
    action_items = models.TextField(
        blank=True, help_text="Action items and assignments"
    )
    decisions = models.TextField(blank=True, help_text="Key decisions made")
    next_meeting_date = models.DateTimeField(
        null=True, blank=True, help_text="Date of next meeting (if agreed)"
    )

    attachment = models.FileField(upload_to="meetings/minutes/", blank=True, null=True)

    # Workflow
    drafted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="drafted_minutes"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_minutes",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_minutes",
    )
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_minutes",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    drafted_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meeting Minutes"
        verbose_name_plural = "Meeting Minutes"

    def __str__(self):
        return f"Minutes — {self.meeting.title}"

    @property
    def is_published(self):
        return self.status == "published"

    @property
    def can_be_submitted(self):
        return self.status == "draft"

    @property
    def can_be_approved(self):
        return self.status in ("submitted", "reviewed")


class MeetingAttendance(models.Model):
    """Track attendance per meeting per user"""

    STATUS_CHOICES = [
        ("attended", "Attended"),
        ("absent", "Absent"),
        ("apologies", "Absent with Apologies"),
        ("late", "Attended (Late)"),
        ("partial", "Partial Attendance"),
        ("no_response", "No Response"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ← fixed: was 'meetingattendance_set', now 'attendance_records' (consistent with model)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="attendance_records"
    )
    attendee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="no_response"
    )
    notes = models.TextField(blank=True)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    # RSVP
    rsvp_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("declined", "Declined"),
            ("tentative", "Tentative"),
        ],
        default="pending",
    )
    rsvp_at = models.DateTimeField(null=True, blank=True)
    rsvp_notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="recorded_attendance"
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["meeting", "attendee__first_name"]
        verbose_name = "Meeting Attendance"
        verbose_name_plural = "Meeting Attendance"
        unique_together = ["meeting", "attendee"]

    def __str__(self):
        return f"{self.attendee.get_full_name()} — {self.meeting.title}"

    @property
    def duration_present(self):
        """Minutes present (if check-in/out recorded)"""
        if self.check_in_time and self.check_out_time:
            delta = self.check_out_time - self.check_in_time
            return int(delta.total_seconds() / 60)
        return None


class MeetingAction(models.Model):
    """Action items arising from a meeting"""

    PRIORITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="actions"
    )
    agenda_item = models.ForeignKey(
        AgendaItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_meeting_actions",
    )
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="medium"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    completion_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_meeting_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "priority"]
        verbose_name = "Meeting Action"
        verbose_name_plural = "Meeting Actions"

    def __str__(self):
        return f"{self.title} — {self.meeting.title}"

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ("completed", "cancelled"):
            return self.due_date < timezone.now().date()
        return False
