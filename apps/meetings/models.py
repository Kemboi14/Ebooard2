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

    # AI Recording Options
    auto_transcribe = models.BooleanField(
        default=False,
        help_text="Automatically transcribe meeting recordings using AI"
    )
    auto_summarize = models.BooleanField(
        default=False,
        help_text="Automatically generate meeting summaries using AI"
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

    E_SIGNATURE_STATUS_CHOICES = [
        ('not_required', 'Not Required'),
        ('pending', 'Pending Signatures'),
        ('partial', 'Partially Signed'),
        ('complete', 'Fully Signed'),
        ('failed', 'Failed'),
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

    # E-signature integration
    e_signature_required = models.BooleanField(default=False, help_text="Require e-signatures for approval")
    e_signature_status = models.CharField(max_length=20, choices=E_SIGNATURE_STATUS_CHOICES, default='not_required')
    e_signature_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for collecting signatures")
    signatories = models.ManyToManyField(User, blank=True, related_name='minutes_to_sign', help_text="Users who need to sign")
    
    # External e-signature integration (DocuSign, Adobe Sign)
    external_signature_id = models.CharField(max_length=200, blank=True, help_text="ID from external e-signature service")
    external_signature_url = models.URLField(blank=True, help_text="URL to external signature document")
    external_signature_provider = models.CharField(max_length=50, blank=True, help_text="e.g., docusign, adobe_sign")

    # Retention policy
    retention_period_years = models.PositiveIntegerField(default=7, help_text="Years to retain these minutes before archiving")
    archive_date = models.DateTimeField(null=True, blank=True, help_text="Date when minutes were archived")
    is_archived = models.BooleanField(default=False, help_text="Whether these minutes have been archived")

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
    
    @property
    def e_signatures_complete(self):
        """Check if all required signatures have been collected"""
        if not self.e_signature_required:
            return True
        if self.e_signature_status == 'complete':
            return True
        return False


class MeetingAttendance(models.Model):
    """
    Track attendance per meeting per user.
    
    Attendees list source:
    - Primary source: meeting.required_attendees (manually added attendees)
    - Secondary source: automatic inclusion based on committee membership (if meeting is committee-specific)
    - Manual additions: can be added individually by meeting organizers
    """

    STATUS_CHOICES = [
        ("attended", "Attended"),
        ("absent", "Absent"),
        ("apologies", "Absent with Apologies"),
        ("late", "Attended (Late)"),
        ("partial", "Partial Attendance"),
        ("no_response", "No Response"),
    ]

    ATTENDEE_SOURCE_CHOICES = [
        ('required', 'Required Attendee'),
        ('committee', 'Committee Member'),
        ('manual', 'Manually Added'),
        ('invitation', 'Invited Guest'),
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
    attendee_source = models.CharField(
        max_length=20,
        choices=ATTENDEE_SOURCE_CHOICES,
        default='manual',
        help_text="How this attendee was added to the meeting"
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


class AnnualMeeting(models.Model):
    """Track annual statutory meetings for compliance"""

    COMPLIANCE_STATUS_CHOICES = [
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('pending', 'Pending Review'),
        ('overdue', 'Overdue'),
        ('waived', 'Waived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Year and organization
    year = models.PositiveIntegerField(help_text="Fiscal year for this annual meeting")
    organization = models.ForeignKey(
        'agencies.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='annual_meetings',
        help_text="Organization/Branch this annual meeting belongs to"
    )
    
    # The actual meeting
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='annual_meeting_record',
        help_text="The actual meeting record"
    )
    
    # Statutory requirements
    statutory_requirements = models.TextField(
        blank=True,
        help_text="Statutory requirements for this annual meeting"
    )
    requirements_met = models.TextField(
        blank=True,
        help_text="Documentation of requirements that were met"
    )
    
    # Compliance status
    compliance_status = models.CharField(
        max_length=20,
        choices=COMPLIANCE_STATUS_CHOICES,
        default='pending'
    )
    compliance_notes = models.TextField(
        blank=True,
        help_text="Notes on compliance status"
    )
    
    # Audit and review
    audit_report = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='annual_meeting_audits',
        help_text="Audit report for this annual meeting"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_annual_meetings',
        help_text="Who reviewed the compliance"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Deadlines
    required_by_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date by which annual meeting must be held"
    )
    actual_date = models.DateField(
        null=True,
        blank=True,
        help_text="Actual date when annual meeting was held"
    )
    
    # Attendance tracking
    required_attendees = models.ManyToManyField(
        User,
        blank=True,
        related_name='required_annual_meetings',
        help_text="Attendees required for compliance"
    )
    actual_attendees = models.ManyToManyField(
        User,
        blank=True,
        related_name='attended_annual_meetings',
        help_text="Actual attendees"
    )
    
    # Resolutions and decisions
    resolutions_passed = models.TextField(
        blank=True,
        help_text="Summary of resolutions passed"
    )
    key_decisions = models.TextField(
        blank=True,
        help_text="Key decisions made during the meeting"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_annual_meetings'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Annual Meeting'
        verbose_name_plural = 'Annual Meetings'
        ordering = ['-year']
        unique_together = ['year', 'organization']
        indexes = [
            models.Index(fields=['year']),
            models.Index(fields=['organization']),
            models.Index(fields=['compliance_status']),
            models.Index(fields=['required_by_date']),
        ]
    
    def __str__(self):
        org_name = self.organization.name if self.organization else 'Organization'
        return f"{org_name} - Annual Meeting {self.year}"
    
    @property
    def is_overdue(self):
        """Check if annual meeting is overdue"""
        if self.required_by_date and not self.actual_date:
            return timezone.now().date() > self.required_by_date
        return False
    
    @property
    def attendance_rate(self):
        """Calculate attendance rate"""
        required_count = self.required_attendees.count()
        if required_count == 0:
            return 0
        actual_count = self.actual_attendees.count()
        return (actual_count / required_count) * 100
    
    @property
    def days_until_deadline(self):
        """Days until required deadline"""
        if self.required_by_date:
            delta = self.required_by_date - timezone.now().date()
            return delta.days
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

    REMINDER_FREQUENCY_CHOICES = [
        ("none", "No Reminders"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("bi_weekly", "Bi-Weekly"),
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

    # Reminder settings
    reminder_frequency = models.CharField(
        max_length=20, choices=REMINDER_FREQUENCY_CHOICES, default="weekly"
    )
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)

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

    def send_reminder(self):
        """Send reminder notification for this action item"""
        if not self.assigned_to or self.status in ("completed", "cancelled"):
            return False
        
        from apps.notifications.views import create_notification
        
        create_notification(
            recipient=self.assigned_to,
            title=f"Action Item Reminder: {self.title}",
            message=f"Your action item '{self.title}' is due on {self.due_date}. Current status: {self.get_status_display()}.",
            notification_type="system_update",
            priority=self.priority,
            action_url=f"/meetings/{self.meeting.id}/",
        )
        
        self.reminder_sent_at = timezone.now()
        self.reminder_count += 1
        self.save(update_fields=['reminder_sent_at', 'reminder_count'])
        
        return True


class QuorumCheck(models.Model):
    """Track quorum checks for meetings"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='quorum_checks')
    
    # Check details
    checked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='quorum_checks')
    checked_at = models.DateTimeField(auto_now_add=True)
    
    # Attendance at time of check
    attendees_present = models.PositiveIntegerField(help_text="Number of attendees present")
    attendees_list = models.ManyToManyField(User, blank=True, related_name='quorum_attendances')
    
    # Quorum status
    quorum_met = models.BooleanField(help_text="Whether quorum was met at time of check")
    quorum_required = models.PositiveIntegerField(help_text="Quorum requirement at time of check")
    
    # Notes
    notes = models.TextField(blank=True, help_text="Notes about the quorum check")
    
    class Meta:
        verbose_name = 'Quorum Check'
        verbose_name_plural = 'Quorum Checks'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['meeting', '-checked_at']),
            models.Index(fields=['checked_by', '-checked_at']),
        ]
    
    def __str__(self):
        status = "Met" if self.quorum_met else "Not Met"
        return f"{self.meeting.title} - Quorum {status} ({self.checked_at.strftime('%Y-%m-%d %H:%M')})"


class AgendaComment(models.Model):
    """Comments and collaboration on agenda items"""

    COMMENT_TYPE_CHOICES = [
        ('suggestion', 'Suggestion'),
        ('question', 'Question'),
        ('clarification', 'Clarification'),
        ('approval', 'Approval'),
        ('concern', 'Concern'),
        ('general', 'General Comment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agenda_item = models.ForeignKey(AgendaItem, on_delete=models.CASCADE, related_name='comments')
    
    # Comment details
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='agenda_comments')
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPE_CHOICES, default='general')
    content = models.TextField(help_text="Comment content")
    
    # Resolution
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_agenda_comments')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, help_text="Notes on how the comment was resolved")
    
    # Parent comment for threaded discussions
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Attachments
    attachments = models.ManyToManyField('documents.Document', blank=True, related_name='agenda_comments')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Agenda Comment'
        verbose_name_plural = 'Agenda Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agenda_item', '-created_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['resolved']),
        ]
    
    def __str__(self):
        return f"{self.author.get_full_name() if self.author else 'Unknown'} - {self.agenda_item.title}"
    
    def resolve(self, user, notes=''):
        """Mark comment as resolved"""
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save(update_fields=['resolved', 'resolved_by', 'resolved_at', 'resolution_notes', 'updated_at'])


class AgendaSuggestion(models.Model):
    """Suggested changes to agenda items"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('deferred', 'Deferred'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agenda_item = models.ForeignKey(AgendaItem, on_delete=models.CASCADE, related_name='suggestions')
    
    # Suggestion details
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='agenda_suggestions')
    field_name = models.CharField(max_length=100, help_text="Field being modified (e.g., title, description)")
    original_value = models.TextField(help_text="Original value")
    suggested_value = models.TextField(help_text="Suggested new value")
    reason = models.TextField(help_text="Reason for the suggestion")
    
    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_agenda_suggestions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Notes on the review decision")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Agenda Suggestion'
        verbose_name_plural = 'Agenda Suggestions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agenda_item', '-created_at']),
            models.Index(fields=['suggested_by', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.suggested_by.get_full_name() if self.suggested_by else 'Unknown'} - {self.field_name}"
    
    def accept(self, reviewer, notes=''):
        """Accept the suggestion and apply the change"""
        self.status = 'accepted'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if notes:
            self.review_notes = notes
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])
        
        # Apply the change to the agenda item
        setattr(self.agenda_item, self.field_name, self.suggested_value)
        self.agenda_item.save(update_fields=[self.field_name, 'updated_at'])
    
    def reject(self, reviewer, notes=''):
        """Reject the suggestion"""
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if notes:
            self.review_notes = notes
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])


class BoardPack(models.Model):
    """Board pack (meeting materials) generation and distribution"""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('distributed', 'Distributed'),
        ('archived', 'Archived'),
    ]

    DISTRIBUTION_METHOD_CHOICES = [
        ('email', 'Email'),
        ('portal', 'Portal'),
        ('both', 'Email and Portal'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='board_pack')
    
    # Pack details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Distribution
    distribution_method = models.CharField(max_length=20, choices=DISTRIBUTION_METHOD_CHOICES, default='portal')
    distribution_date = models.DateTimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(User, blank=True, related_name='board_packs')
    cc_recipients = models.ManyToManyField(User, blank=True, related_name='cc_board_packs')
    
    # Documents included
    documents = models.ManyToManyField('documents.Document', blank=True, related_name='board_packs')
    
    # Generated pack file
    pack_file = models.FileField(upload_to='board_packs/', null=True, blank=True)
    pack_size = models.PositiveIntegerField(null=True, blank=True, help_text="Size in bytes")
    
    # Cover page
    include_cover_page = models.BooleanField(default=True)
    cover_title = models.CharField(max_length=200, blank=True)
    cover_message = models.TextField(blank=True)
    
    # Table of contents
    include_toc = models.BooleanField(default=True)
    
    # Version
    version = models.PositiveIntegerField(default=1)
    
    # Notifications
    send_notification = models.BooleanField(default=True)
    notification_message = models.TextField(blank=True)
    
    # Tracking
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    
    # Author
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_board_packs')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Board Pack'
        verbose_name_plural = 'Board Packs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['meeting', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['distribution_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.meeting.title}"
    
    @property
    def is_ready(self):
        """Check if pack is ready for distribution"""
        return self.status in ('ready', 'distributed', 'archived')
    
    @property
    def file_size_display(self):
        """Display file size in human-readable format"""
        if not self.pack_size:
            return "N/A"
        if self.pack_size < 1024:
            return f"{self.pack_size} B"
        elif self.pack_size < 1024**2:
            return f"{self.pack_size / 1024:.1f} KB"
        elif self.pack_size < 1024**3:
            return f"{self.pack_size / 1024**2:.1f} MB"
        return f"{self.pack_size / 1024**3:.1f} GB"


class BoardPackAccessLog(models.Model):
    """Track access and downloads of board packs"""

    ACTION_CHOICES = [
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('emailed', 'Emailed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board_pack = models.ForeignKey(BoardPack, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='board_pack_access_logs')
    
    # Access details
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamp
    accessed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Board Pack Access Log'
        verbose_name_plural = 'Board Pack Access Logs'
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['board_pack', '-accessed_at']),
            models.Index(fields=['user', '-accessed_at']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        user = self.user.get_full_name() if self.user else 'Anonymous'
        return f"{user} - {self.get_action_display()} - {self.board_pack.title}"
