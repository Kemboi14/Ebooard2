import uuid
import json
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.accounts.models import User

class Meeting(models.Model):
    """Meeting model for board meetings and governance sessions with enhanced video conferencing"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]
    
    TYPE_CHOICES = [
        ('board', 'Board Meeting'),
        ('committee', 'Committee Meeting'),
        ('agm', 'Annual General Meeting'),
        ('emergency', 'Emergency Meeting'),
        ('workshop', 'Workshop/Training'),
    ]
    
    VIDEO_PLATFORM_CHOICES = [
        ('', 'No Virtual Meeting'),
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('google_meet', 'Google Meet'),
        ('webex', 'Cisco Webex'),
        ('skype', 'Skype'),
        ('jitsi', 'Jitsi Meet'),
        ('whereby', 'Whereby'),
        ('other', 'Other Platform'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='board')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Scheduling
    scheduled_date = models.DateTimeField()
    scheduled_end_time = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True, help_text="Physical location (leave blank for virtual only)")
    
    # Enhanced Video Conferencing
    is_virtual = models.BooleanField(default=False, help_text="Enable virtual meeting")
    virtual_platform = models.CharField(
        max_length=50,
        choices=VIDEO_PLATFORM_CHOICES,
        default='',
        blank=True,
        help_text="Virtual meeting platform"
    )
    virtual_meeting_url = models.URLField(blank=True, help_text="Virtual meeting link")
    virtual_meeting_id = models.CharField(max_length=100, blank=True, help_text="Meeting ID/Room ID")
    virtual_meeting_password = models.CharField(max_length=50, blank=True, help_text="Meeting password")
    virtual_dial_in = models.CharField(max_length=50, blank=True, help_text="Dial-in phone number")
    
    # Video Conferencing Settings
    enable_recording = models.BooleanField(default=False, help_text="Record the meeting")
    enable_chat = models.BooleanField(default=True, help_text="Enable meeting chat")
    enable_screen_sharing = models.BooleanField(default=True, help_text="Enable screen sharing")
    enable_breakout_rooms = models.BooleanField(default=False, help_text="Enable breakout rooms")
    enable_waiting_room = models.BooleanField(default=True, help_text="Enable waiting room")
    max_participants = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum participants (leave unlimited)")
    
    # Meeting details
    agenda = models.TextField(blank=True, help_text="Meeting agenda items")
    
    # Organizers and attendees
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='organized_meetings')
    attendees = models.ManyToManyField(User, related_name='meeting_attendees', blank=True)
    required_attendees = models.ManyToManyField(User, related_name='required_meeting_attendees', blank=True)
    
    # Video Conferencing Integration Data
    platform_data = models.JSONField(default=dict, blank=True, help_text="Platform-specific data (API responses, etc.)")
    recording_url = models.URLField(blank=True, help_text="Recording URL after meeting")
    recording_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Recording duration in minutes")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_meetings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = 'Meeting'
        verbose_name_plural = 'Meetings'
        indexes = [
            models.Index(fields=['scheduled_date', 'status']),
            models.Index(fields=['virtual_platform']),
            models.Index(fields=['organizer', '-scheduled_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.scheduled_date.strftime('%b %d, %Y')}"
    
    def clean(self):
        """Validate meeting data"""
        if self.is_virtual and not self.virtual_platform:
            raise ValidationError("Virtual meeting platform must be selected for virtual meetings.")
        
        if self.virtual_platform and not self.virtual_meeting_url:
            raise ValidationError("Virtual meeting URL is required when platform is selected.")
        
        if self.scheduled_end_time and self.scheduled_end_time <= self.scheduled_date:
            raise ValidationError("End time must be after start time.")
    
    @property
    def is_upcoming(self):
        """Check if meeting is upcoming"""
        return self.scheduled_date > timezone.now() and self.status == 'scheduled'
    
    @property
    def is_in_progress(self):
        """Check if meeting is currently in progress"""
        now = timezone.now()
        return (self.scheduled_date <= now <= self.scheduled_end_time and 
                self.status == 'in_progress')
    
    @property
    def duration_minutes(self):
        """Calculate meeting duration in minutes"""
        if self.scheduled_end_time:
            delta = self.scheduled_end_time - self.scheduled_date
            return int(delta.total_seconds() / 60)
        return 0
    
    @property
    def has_recording(self):
        """Check if meeting has recording"""
        return bool(self.recording_url)
    
    @property
    def platform_display(self):
        """Get platform display name"""
        return dict(self.VIDEO_PLATFORM_CHOICES).get(self.virtual_platform, 'Unknown')
    
    def get_absolute_url(self):
        """Get absolute URL for meeting"""
        return f"/meetings/{self.id}/"
    
    def generate_meeting_link(self):
        """Generate meeting link based on platform"""
        if self.virtual_platform == 'zoom' and self.virtual_meeting_id:
            return f"https://zoom.us/j/{self.virtual_meeting_id}"
        elif self.virtual_platform == 'teams':
            return self.virtual_meeting_url
        elif self.virtual_platform == 'google_meet':
            return self.virtual_meeting_url
        elif self.virtual_platform == 'webex':
            return self.virtual_meeting_url
        else:
            return self.virtual_meeting_url
    
    def get_join_instructions(self):
        """Get platform-specific join instructions"""
        instructions = []
        
        if self.virtual_platform == 'zoom':
            instructions.append("Join via Zoom using the link above")
            if self.virtual_meeting_id:
                instructions.append(f"Meeting ID: {self.virtual_meeting_id}")
            if self.virtual_meeting_password:
                instructions.append(f"Password: {self.virtual_meeting_password}")
            if self.virtual_dial_in:
                instructions.append(f"Dial-in: {self.virtual_dial_in}")
        
        elif self.virtual_platform == 'teams':
            instructions.append("Click the link to join via Microsoft Teams")
            instructions.append("Ensure you have the Teams app installed")
        
        elif self.virtual_platform == 'google_meet':
            instructions.append("Click the link to join via Google Meet")
            instructions.append("Use Google Chrome for best experience")
        
        return instructions

class VideoConferenceSession(models.Model):
    """Track individual video conference sessions"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='video_sessions')
    
    # Session details
    session_id = models.CharField(max_length=200, unique=True, help_text="Platform session ID")
    platform = models.CharField(max_length=50, choices=Meeting.VIDEO_PLATFORM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Participants
    participant_count = models.PositiveIntegerField(default=0)
    peak_participants = models.PositiveIntegerField(default=0)
    
    # Recording
    recording_started_at = models.DateTimeField(null=True, blank=True)
    recording_ended_at = models.DateTimeField(null=True, blank=True)
    recording_file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Platform data
    platform_data = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Video Conference Session'
        verbose_name_plural = 'Video Conference Sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['meeting', '-created_at']),
            models.Index(fields=['platform', 'status']),
        ]
    
    def __str__(self):
        return f"{self.meeting.title} - {self.platform} Session"
    
    @property
    def is_active(self):
        """Check if session is currently active"""
        return self.status == 'active'
    
    @property
    def duration_display(self):
        """Get human-readable duration"""
        if self.duration_minutes:
            if self.duration_minutes < 60:
                return f"{self.duration_minutes} minutes"
            else:
                hours = self.duration_minutes // 60
                minutes = self.duration_minutes % 60
                return f"{hours}h {minutes}m"
        return "N/A"

class VideoConferenceParticipant(models.Model):
    """Track participants in video conference sessions"""
    
    ROLE_CHOICES = [
        ('host', 'Host'),
        ('co_host', 'Co-host'),
        ('presenter', 'Presenter'),
        ('attendee', 'Attendee'),
        ('panelist', 'Panelist'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(VideoConferenceSession, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='video_sessions')
    
    # Participant details
    email = models.EmailField(help_text="Participant email")
    display_name = models.CharField(max_length=200, help_text="Display name in meeting")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='attendee')
    
    # Join/Leave times
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Platform data
    platform_participant_id = models.CharField(max_length=200, blank=True, help_text="Platform participant ID")
    platform_data = models.JSONField(default=dict, blank=True)
    
    # Status
    attended = models.BooleanField(default=False)
    was_recording = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Video Conference Participant'
        verbose_name_plural = 'Video Conference Participants'
        ordering = ['joined_at']
        indexes = [
            models.Index(fields=['session', '-joined_at']),
            models.Index(fields=['user', '-joined_at']),
        ]
    
    def __str__(self):
        return f"{self.display_name} - {self.session.meeting.title}"
    
    @property
    def attendance_duration(self):
        """Get formatted attendance duration"""
        if self.duration_minutes:
            if self.duration_minutes < 60:
                return f"{self.duration_minutes} min"
            else:
                hours = self.duration_minutes // 60
                minutes = self.duration_minutes % 60
                return f"{hours}h {minutes}m"
        return "N/A"

class VideoConferenceRecording(models.Model):
    """Manage video conference recordings"""
    
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('available', 'Available'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(VideoConferenceSession, on_delete=models.CASCADE, related_name='recordings')
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='recordings')
    
    # Recording details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    
    # File information
    file_url = models.URLField(help_text="Recording URL")
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    duration_seconds = models.PositiveIntegerField(help_text="Recording duration in seconds")
    format = models.CharField(max_length=20, default='mp4', help_text="Video format")
    
    # Access control
    is_public = models.BooleanField(default=False, help_text="Make recording publicly accessible")
    access_password = models.CharField(max_length=50, blank=True, help_text="Password for private recordings")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Recording expiration date")
    
    # Platform data
    platform_recording_id = models.CharField(max_length=200, blank=True, help_text="Platform recording ID")
    platform_data = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Video Conference Recording'
        verbose_name_plural = 'Video Conference Recordings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['meeting', '-created_at']),
            models.Index(fields=['session', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.meeting.title}"
    
    @property
    def file_size_display(self):
        """Get human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"
    
    @property
    def duration_display(self):
        """Get human-readable duration"""
        if self.duration_seconds:
            hours = self.duration_seconds // 3600
            minutes = (self.duration_seconds % 3600) // 60
            seconds = self.duration_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "N/A"
    
    @property
    def is_expired(self):
        """Check if recording has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_absolute_url(self):
        """Get absolute URL for recording"""
        return f"/meetings/recordings/{self.id}/"

# Keep existing models
class AgendaItem(models.Model):
    """Agenda items for meetings"""
    
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='agenda_items')
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    order = models.PositiveIntegerField(default=0)
    estimated_duration = models.PositiveIntegerField(help_text="Estimated duration in minutes", default=15)
    
    # Attachments
    attachment = models.FileField(upload_to='meetings/agenda_attachments/', blank=True, null=True)
    
    # Presenter/Owner
    presenter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='presented_agenda')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_agenda')
    
    # Status
    is_discussed = models.BooleanField(default=False)
    decision = models.TextField(blank=True, help_text="Decision made on this agenda item")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Agenda Item'
        verbose_name_plural = 'Agenda Items'
    
    def __str__(self):
        return f"{self.meeting.title} - {self.title}"


class MeetingMinutes(models.Model):
    """Meeting minutes for formal record keeping"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='meeting_minutes')
    content = models.TextField(help_text="Full meeting minutes content")
    action_items = models.TextField(blank=True, help_text="Action items and assignments")
    
    # Attachments
    attachment = models.FileField(upload_to='meetings/minutes/', blank=True, null=True)
    
    # Approval workflow
    drafted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='drafted_minutes')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviewed_minutes')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_minutes')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted for Review'),
            ('approved', 'Approved'),
            ('published', 'Published'),
        ],
        default='draft'
    )
    
    # Metadata
    drafted_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Meeting Minutes'
        verbose_name_plural = 'Meeting Minutes'
    
    def __str__(self):
        return f"Minutes for {self.meeting.title}"


class MeetingAttendance(models.Model):
    """Track meeting attendance"""
    
    STATUS_CHOICES = [
        ('attended', 'Attended'),
        ('absent', 'Absent'),
        ('apologies', 'Absent with Apologies'),
        ('no_response', 'No Response'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendance_records')
    attendee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='no_response')
    
    # Additional details
    notes = models.TextField(blank=True, help_text="Reason for absence or additional notes")
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_attendance')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['meeting', 'attendee']
        verbose_name = 'Meeting Attendance'
        verbose_name_plural = 'Meeting Attendance'
        unique_together = ['meeting', 'attendee']
    
    def __str__(self):
        return f"{self.attendee.get_full_name()} - {self.meeting.title}"
