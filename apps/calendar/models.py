from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class CalendarEvent(models.Model):
    """
    Unified calendar event model that aggregates events from all apps.
    Events are automatically created/updated via Django signals.
    """
    EVENT_TYPE_CHOICES = [
        ("meeting", "Meeting"),
        ("voting_deadline", "Voting Deadline"),
        ("document_due", "Document Due Date"),
        ("risk_review", "Risk Review"),
        ("audit_date", "Audit Date"),
        ("committee_meeting", "Committee Meeting"),
        ("discussion_event", "Discussion Event"),
        ("esignature_deadline", "E-Signature Deadline"),
        ("governance_event", "Governance Event"),
        ("compliance_deadline", "Compliance Deadline"),
        ("policy_expiry", "Policy Expiry"),
        ("annual_meeting", "Annual Meeting"),
        ("training", "Training Session"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    
    # Source information
    source_app = models.CharField(max_length=50)  # e.g., 'meetings', 'voting', 'documents'
    source_model = models.CharField(max_length=50)  # e.g., 'Meeting', 'Motion'
    source_object_id = models.UUIDField()
    
    # Timing
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    all_day = models.BooleanField(default=False)
    
    # User association
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_events",
        blank=True,
        null=True,
    )
    
    # Additional metadata
    location = models.CharField(max_length=255, blank=True, null=True)
    color = models.CharField(max_length=7, default="#7dc143")  # Hex color code
    status = models.CharField(max_length=50, blank=True, null=True)
    
    # Priority and importance
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        default='medium'
    )
    
    # Reminder settings
    reminder_enabled = models.BooleanField(default=True)
    reminder_minutes_before = models.PositiveIntegerField(
        default=15,
        help_text="Minutes before event to send reminder"
    )
    reminder_sent = models.BooleanField(default=False)
    
    # Recurrence
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., daily, weekly, monthly, yearly"
    )
    recurrence_end_date = models.DateTimeField(null=True, blank=True)
    
    # Compliance specific
    compliance_category = models.CharField(max_length=100, blank=True, help_text="Compliance category for compliance deadlines")
    is_mandatory = models.BooleanField(default=False, help_text="Whether attendance/action is mandatory")
    
    # Governance specific
    governance_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('board', 'Board'),
            ('committee', 'Committee'),
            ('statutory', 'Statutory'),
            ('regulatory', 'Regulatory'),
        ],
        help_text="Type of governance event"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_events"
        ordering = ["start_date"]
        indexes = [
            models.Index(fields=["start_date"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["source_app", "source_object_id"]),
            models.Index(fields=["user"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["compliance_category"]),
            models.Index(fields=["governance_type"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_event_type_display()})"
    
    @property
    def is_upcoming(self):
        """Check if event is in the future"""
        return self.start_date > timezone.now()
    
    @property
    def is_past(self):
        """Check if event has passed"""
        return self.end_date and self.end_date < timezone.now()
    
    @property
    def is_today(self):
        """Check if event is today"""
        today = timezone.now().date()
        return self.start_date.date() == today
    
    @property
    def days_until(self):
        """Days until event"""
        if self.is_upcoming:
            delta = self.start_date - timezone.now()
            return delta.days
        return 0
    
    @property
    def needs_reminder(self):
        """Check if reminder should be sent"""
        if not self.reminder_enabled or self.reminder_sent:
            return False
        if self.is_past:
            return False
        minutes_until = (self.start_date - timezone.now()).total_seconds() / 60
        return minutes_until <= self.reminder_minutes_before


class CalendarConfigurator(models.Model):
    """
    Configure which models should be included in the super calendar.
    Similar to Odoo's calendar configurator but more flexible.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Source configuration
    source_app = models.CharField(max_length=50)
    source_model = models.CharField(max_length=50)
    
    # Field mappings
    title_field = models.CharField(max_length=100)
    description_field = models.CharField(max_length=100, blank=True, null=True)
    start_date_field = models.CharField(max_length=100)
    end_date_field = models.CharField(max_length=100, blank=True, null=True)
    all_day_field = models.CharField(max_length=100, blank=True, null=True)
    user_field = models.CharField(max_length=100, blank=True, null=True)
    location_field = models.CharField(max_length=100, blank=True, null=True)
    status_field = models.CharField(max_length=100, blank=True, null=True)
    
    # Event type mapping
    event_type = models.CharField(
        max_length=50,
        choices=CalendarEvent.EVENT_TYPE_CHOICES,
        default="other",
    )
    
    # Display options
    color = models.CharField(max_length=7, default="#7dc143")
    is_active = models.BooleanField(default=True)
    
    # Filtering
    filter_condition = models.JSONField(blank=True, null=True)  # For complex filtering
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "calendar_configurators"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.source_app}.{self.source_model})"


class UserCalendarPreference(models.Model):
    """
    User-specific calendar preferences for customization.
    """
    VIEW_CHOICES = [
        ("month", "Month"),
        ("week", "Week"),
        ("day", "Day"),
        ("agenda", "Agenda"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_preferences",
    )
    
    default_view = models.CharField(max_length=20, choices=VIEW_CHOICES, default="month")
    
    # Filter preferences
    show_event_types = models.JSONField(default=list)  # List of event types to show
    show_my_events_only = models.BooleanField(default=False)
    
    # Display preferences
    start_of_week = models.IntegerField(default=0)  # 0 = Sunday, 1 = Monday, etc.
    show_weekends = models.BooleanField(default=True)
    
    # Notification preferences
    email_reminders = models.BooleanField(default=True)
    reminder_hours_before = models.IntegerField(default=24)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_calendar_preferences"

    def __str__(self):
        return f"{self.user.email} - Calendar Preferences"


class ExternalCalendarConnection(models.Model):
    """External calendar provider connections (Google, Outlook, etc.)"""

    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Microsoft Outlook'),
        ('office365', 'Office 365'),
        ('exchange', 'Microsoft Exchange'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
        ('revoked', 'Access Revoked'),
    ]

    SYNC_DIRECTION_CHOICES = [
        ('bidirectional', 'Bidirectional'),
        ('to_external', 'To External Only'),
        ('from_external', 'From External Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_connections')
    
    # Provider details
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # OAuth tokens
    access_token = models.TextField(blank=True, help_text="OAuth access token (encrypted)")
    refresh_token = models.TextField(blank=True, help_text="OAuth refresh token (encrypted)")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Calendar details
    external_calendar_id = models.CharField(max_length=255, blank=True, help_text="External calendar ID")
    calendar_name = models.CharField(max_length=255, blank=True, help_text="Name of the external calendar")
    calendar_color = models.CharField(max_length=7, blank=True, help_text="Calendar color hex code")
    
    # Sync configuration
    sync_direction = models.CharField(max_length=20, choices=SYNC_DIRECTION_CHOICES, default='bidirectional')
    auto_sync = models.BooleanField(default=True, help_text="Automatically sync events")
    sync_interval_minutes = models.PositiveIntegerField(default=30, help_text="Sync interval in minutes")
    
    # Event filtering
    sync_meeting_events = models.BooleanField(default=True)
    sync_voting_events = models.BooleanField(default=True)
    sync_document_events = models.BooleanField(default=True)
    sync_other_events = models.BooleanField(default=False)
    
    # Sync status
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, blank=True)
    last_sync_error = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'External Calendar Connection'
        verbose_name_plural = 'External Calendar Connections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['status']),
            models.Index(fields=['last_sync_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_provider_display()}"
    
    @property
    def is_connected(self):
        """Check if connection is active and tokens are valid"""
        if self.status != 'active':
            return False
        if self.token_expires_at and timezone.now() >= self.token_expires_at:
            return False
        return True


class CalendarSyncLog(models.Model):
    """Log of calendar synchronization operations"""

    SYNC_STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(ExternalCalendarConnection, on_delete=models.CASCADE, related_name='sync_logs')
    
    # Sync details
    sync_status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES)
    events_synced_to_external = models.PositiveIntegerField(default=0)
    events_synced_from_external = models.PositiveIntegerField(default=0)
    events_updated = models.PositiveIntegerField(default=0)
    events_created = models.PositiveIntegerField(default=0)
    events_deleted = models.PositiveIntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(null=True, blank=True)
    
    # Performance
    sync_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Calendar Sync Log'
        verbose_name_plural = 'Calendar Sync Logs'
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['connection', '-synced_at']),
            models.Index(fields=['sync_status', '-synced_at']),
        ]
    
    def __str__(self):
        return f"{self.connection} - {self.get_sync_status_display()} ({self.synced_at})"
