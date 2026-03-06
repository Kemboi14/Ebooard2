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
