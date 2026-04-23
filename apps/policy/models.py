from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class PolicyCategory(models.Model):
    """Categories for organizing policies"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Policy Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_full_path(self):
        """Get the full category path including parent categories"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name

class Policy(models.Model):
    """Board governance policies"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived'),
        ('superseded', 'Superseded'),
    ]
    
    CATEGORY_TYPES = [
        ('governance', 'Governance'),
        ('compliance', 'Compliance'),
        ('risk_management', 'Risk Management'),
        ('financial', 'Financial'),
        ('operational', 'Operational'),
        ('ethical', 'Ethical'),
        ('safety', 'Safety'),
        ('environmental', 'Environmental'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField(help_text="Full policy content")
    category = models.ForeignKey(PolicyCategory, on_delete=models.SET_NULL, null=True, blank=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='governance')
    
    # Version control
    version = models.CharField(max_length=20, default="1.0")
    is_current = models.BooleanField(default=True)
    supersedes = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='superseded_by')
    
    # Status and workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Metadata
    effective_date = models.DateField(null=True, blank=True, help_text="Date when policy becomes effective")
    review_date = models.DateField(null=True, blank=True, help_text="Next review date")
    expiry_date = models.DateField(null=True, blank=True, help_text="Date when policy expires")
    
    # Responsibility
    policy_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_policies')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_policies')
    
    # Access control
    access_level = models.CharField(max_length=20, choices=[
        ('public', 'Public'),
        ('board', 'Board Only'),
        ('committee', 'Committee'),
        ('management', 'Management'),
        ('restricted', 'Restricted'),
    ], default='board')
    
    # Attachments
    attachment = models.FileField(upload_to='policies/attachments/', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_policies')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_current']),
            models.Index(fields=['category_type']),
            models.Index(fields=['effective_date']),
        ]

    def __str__(self):
        return f"{self.title} v{self.version}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('policies:policy_detail', kwargs={'pk': self.pk})

    @property
    def is_active(self):
        """Check if policy is currently active"""
        if self.status != 'published' or not self.is_current:
            return False
        
        today = timezone.now().date()
        if self.effective_date and today < self.effective_date:
            return False
        if self.expiry_date and today > self.expiry_date:
            return False
        return True

    @property
    def needs_review(self):
        """Check if policy needs review"""
        if not self.review_date:
            return False
        return timezone.now().date() >= self.review_date

    def get_next_version(self):
        """Generate next version number"""
        try:
            current_version = float(self.version)
            next_version = current_version + 0.1
            return f"{next_version:.1f}"
        except ValueError:
            return "2.0"

    def create_new_version(self, content_changes=None, **kwargs):
        """Create a new version of this policy"""
        # Mark current version as not current
        self.is_current = False
        self.save()
        
        # Create new version
        new_policy = Policy.objects.create(
            title=self.title,
            description=kwargs.get('description', self.description),
            content=content_changes or self.content,
            category=self.category,
            category_type=self.category_type,
            version=self.get_next_version(),
            is_current=True,
            supersedes=self,
            status='draft',
            effective_date=kwargs.get('effective_date', self.effective_date),
            review_date=kwargs.get('review_date', self.review_date),
            expiry_date=kwargs.get('expiry_date', self.expiry_date),
            policy_owner=kwargs.get('policy_owner', self.policy_owner),
            access_level=kwargs.get('access_level', self.access_level),
            created_by=kwargs.get('created_by'),
        )
        return new_policy

class PolicyReview(models.Model):
    """Policy review records"""
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    review_date = models.DateField()
    review_type = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled Review'),
        ('ad_hoc', 'Ad Hoc Review'),
        ('compliance', 'Compliance Review'),
        ('incident', 'Incident Review'),
    ])
    findings = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    action_required = models.BooleanField(default=False)
    next_review_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-review_date']

    def __str__(self):
        return f"{self.policy.title} - {self.review_date}"

class PolicyAcknowledgment(models.Model):
    """Track policy acknowledgments by users"""
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='acknowledgments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['policy', 'user']
        ordering = ['-acknowledged_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.policy.title}"


class PolicyExpiryMonitor(models.Model):
    """Monitor policy expiry and send notifications"""

    NOTIFICATION_STATUS_CHOICES = [
        ('not_sent', 'Not Sent'),
        ('sent_30_days', 'Sent 30 Days Before'),
        ('sent_14_days', 'Sent 14 Days Before'),
        ('sent_7_days', 'Sent 7 Days Before'),
        ('sent_1_day', 'Sent 1 Day Before'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='expiry_monitors')
    
    # Expiry tracking
    expiry_date = models.DateField(help_text="Date when policy expires")
    notification_status = models.CharField(
        max_length=20,
        choices=NOTIFICATION_STATUS_CHOICES,
        default='not_sent'
    )
    
    # Notification tracking
    last_notified_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0, help_text="Number of notifications sent")
    
    # Recipients
    notified_users = models.ManyToManyField(User, blank=True, related_name='policy_expiry_notifications')
    
    # Actions taken
    action_taken = models.TextField(blank=True, help_text="Actions taken in response to expiry")
    action_taken_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policy_expiry_actions'
    )
    action_taken_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False, help_text="Whether expiry has been addressed")
    resolution_notes = models.TextField(blank=True, help_text="Notes on how expiry was resolved")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Policy Expiry Monitor'
        verbose_name_plural = 'Policy Expiry Monitors'
        ordering = ['expiry_date']
        unique_together = ['policy', 'expiry_date']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['notification_status']),
            models.Index(fields=['is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.policy.title} - Expires {self.expiry_date}"
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        from datetime import timedelta
        today = timezone.now().date()
        if self.expiry_date >= today:
            return (self.expiry_date - today).days
        return 0
    
    @property
    def is_expired(self):
        """Check if policy has expired"""
        return timezone.now().date() > self.expiry_date
    
    @property
    def needs_notification(self):
        """Check if notification should be sent"""
        if self.is_resolved or self.notification_status == 'expired':
            return False
        
        days = self.days_until_expiry
        
        # Check if we need to send notification at specific intervals
        if days == 30 and self.notification_status == 'not_sent':
            return True
        elif days == 14 and self.notification_status == 'sent_30_days':
            return True
        elif days == 7 and self.notification_status == 'sent_14_days':
            return True
        elif days == 1 and self.notification_status == 'sent_7_days':
            return True
        elif days == 0 and self.notification_status == 'sent_1_day':
            return True
        
        return False
    
    def send_notification(self):
        """Mark notification as sent"""
        from apps.notifications.services.email_service import send_policy_expiry_notification
        
        days = self.days_until_expiry
        
        if days == 30:
            self.notification_status = 'sent_30_days'
        elif days == 14:
            self.notification_status = 'sent_14_days'
        elif days == 7:
            self.notification_status = 'sent_7_days'
        elif days == 1:
            self.notification_status = 'sent_1_day'
        elif days == 0:
            self.notification_status = 'expired'
        
        self.last_notified_at = timezone.now()
        self.notification_count += 1
        self.save(update_fields=['notification_status', 'last_notified_at', 'notification_count'])
        
        # Queue email notification
        try:
            send_policy_expiry_notification.delay(str(self.policy.id), days)
        except Exception:
            # Fallback to synchronous if Celery not available
            send_policy_expiry_notification(str(self.policy.id), days)
