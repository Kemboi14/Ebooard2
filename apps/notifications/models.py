from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid

User = get_user_model()

class Notification(models.Model):
    """Real-time notifications for board members"""
    
    NOTIFICATION_TYPES = [
        ('meeting_reminder', 'Meeting Reminder'),
        ('meeting_update', 'Meeting Update'),
        ('voting_open', 'Voting Open'),
        ('voting_close', 'Voting Closing'),
        ('voting_result', 'Voting Result'),
        ('document_shared', 'Document Shared'),
        ('document_updated', 'Document Updated'),
        ('policy_update', 'Policy Update'),
        ('risk_alert', 'Risk Alert'),
        ('evaluation_assigned', 'Evaluation Assigned'),
        ('evaluation_reminder', 'Evaluation Reminder'),
        ('discussion_reply', 'Discussion Reply'),
        ('discussion_mention', 'Discussion Mention'),
        ('audit_alert', 'Audit Alert'),
        ('system_update', 'System Update'),
        ('security_alert', 'Security Alert'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Recipient
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Related object (optional)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Action URL (where user should go when clicking)
    action_url = models.CharField(max_length=500, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    is_email_sent = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data (JSON for flexibility)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} → {self.recipient.get_full_name()}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def get_absolute_url(self):
        """Get URL for the notification"""
        if self.action_url:
            return self.action_url
        return reverse('notifications:notification_detail', kwargs={'pk': self.pk})

    @property
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def time_since_created(self):
        """Human readable time since creation"""
        from django.utils.timesince import timesince
        return timesince(self.created_at)

class NotificationPreference(models.Model):
    """User notification preferences"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email preferences
    email_meeting_reminders = models.BooleanField(default=True)
    email_voting_notifications = models.BooleanField(default=True)
    email_document_updates = models.BooleanField(default=True)
    email_discussion_replies = models.BooleanField(default=True)
    email_risk_alerts = models.BooleanField(default=True)
    email_audit_alerts = models.BooleanField(default=True)
    email_system_updates = models.BooleanField(default=False)
    
    # In-app preferences
    in_app_meeting_reminders = models.BooleanField(default=True)
    in_app_voting_notifications = models.BooleanField(default=True)
    in_app_document_updates = models.BooleanField(default=True)
    in_app_discussion_replies = models.BooleanField(default=True)
    in_app_risk_alerts = models.BooleanField(default=True)
    in_app_audit_alerts = models.BooleanField(default=True)
    in_app_system_updates = models.BooleanField(default=True)
    
    # Frequency settings
    email_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('never', 'Never'),
        ],
        default='immediate'
    )
    
    # Quiet hours (for non-urgent notifications)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"

    def should_send_email(self, notification_type):
        """Check if user wants email for this notification type"""
        mapping = {
            'meeting_reminder': self.email_meeting_reminders,
            'meeting_update': self.email_meeting_reminders,
            'voting_open': self.email_voting_notifications,
            'voting_close': self.email_voting_notifications,
            'voting_result': self.email_voting_notifications,
            'document_shared': self.email_document_updates,
            'document_updated': self.email_document_updates,
            'discussion_reply': self.email_discussion_replies,
            'discussion_mention': self.email_discussion_replies,
            'risk_alert': self.email_risk_alerts,
            'audit_alert': self.email_audit_alerts,
            'system_update': self.email_system_updates,
        }
        return mapping.get(notification_type, True)

    def should_send_in_app(self, notification_type):
        """Check if user wants in-app notification for this type"""
        mapping = {
            'meeting_reminder': self.in_app_meeting_reminders,
            'meeting_update': self.in_app_meeting_reminders,
            'voting_open': self.in_app_voting_notifications,
            'voting_close': self.in_app_voting_notifications,
            'voting_result': self.in_app_voting_notifications,
            'document_shared': self.in_app_document_updates,
            'document_updated': self.in_app_document_updates,
            'discussion_reply': self.in_app_discussion_replies,
            'discussion_mention': self.in_app_discussion_replies,
            'risk_alert': self.in_app_risk_alerts,
            'audit_alert': self.in_app_audit_alerts,
            'system_update': self.in_app_system_updates,
        }
        return mapping.get(notification_type, True)

    def is_in_quiet_hours(self):
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        current_time = timezone.now().time()
        start_time = self.quiet_hours_start
        end_time = self.quiet_hours_end
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Overnight quiet hours (e.g., 22:00 to 08:00)
            return current_time >= start_time or current_time <= end_time

class NotificationTemplate(models.Model):
    """Templates for common notifications"""
    
    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(max_length=20, choices=Notification.NOTIFICATION_TYPES)
    
    # Template content
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    
    # Email template
    email_subject_template = models.CharField(max_length=200, blank=True)
    email_body_template = models.TextField(blank=True)
    
    # Default settings
    default_priority = models.CharField(max_length=10, choices=Notification.PRIORITY_LEVELS, default='normal')
    default_action_url = models.CharField(max_length=500, blank=True)
    
    # Metadata
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_notification_type_display()})"

    def render_title(self, context):
        """Render title template with context"""
        from django.template import Template, Context
        template = Template(self.title_template)
        return template.render(Context(context))

    def render_message(self, context):
        """Render message template with context"""
        from django.template import Template, Context
        template = Template(self.message_template)
        return template.render(Context(context))

class NotificationBatch(models.Model):
    """Batch notifications for sending multiple notifications efficiently"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Batch details
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=Notification.NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=Notification.PRIORITY_LEVELS, default='normal')
    
    # Recipients
    recipients = models.ManyToManyField(User, related_name='batch_notifications')
    
    # Related object
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Status
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Batch: {self.title} ({self.total_recipients} recipients)"

    def create_notifications(self):
        """Create individual notifications for all recipients"""
        notifications = []
        for recipient in self.recipients.all():
            notification = Notification(
                recipient=recipient,
                title=self.title,
                message=self.message,
                notification_type=self.notification_type,
                priority=self.priority,
                content_type=self.content_type,
                object_id=self.object_id,
                action_url=self.default_action_url,
            )
            notifications.append(notification)
        
        return Notification.objects.bulk_create(notifications)

class NotificationChannel(models.Model):
    """Different channels for sending notifications"""
    
    CHANNEL_TYPES = [
        ('in_app', 'In-App'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('webhook', 'Webhook'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    
    # Configuration (JSON for flexibility)
    configuration = models.JSONField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_sent = models.PositiveIntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"

class NotificationLog(models.Model):
    """Log of all notification attempts"""
    
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='logs')
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name='logs')
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('bounced', 'Bounced'),
        ],
        default='pending'
    )
    
    # Response data
    response_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.notification.title} via {self.channel.name} - {self.status}"
