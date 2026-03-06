from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.urls import reverse
import json

User = get_user_model()

class AuditLog(models.Model):
    """Track all user actions and system events for compliance and security"""
    
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('login_failed', 'Login Failed'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('download', 'Download'),
        ('upload', 'Upload'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('publish', 'Publish'),
        ('archive', 'Archive'),
        ('restore', 'Restore'),
        ('acknowledge', 'Acknowledge'),
        ('vote', 'Vote'),
        ('comment', 'Comment'),
        ('assign', 'Assign'),
        ('unassign', 'Unassign'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    MODULES = [
        ('accounts', 'Accounts'),
        ('dashboard', 'Dashboard'),
        ('meetings', 'Meetings'),
        ('documents', 'Documents'),
        ('voting', 'Voting'),
        ('risk', 'Risk Management'),
        ('policy', 'Policies'),
        ('audit', 'Audit Trail'),
        ('evaluation', 'Board Evaluation'),
        ('discussions', 'Discussions'),
        ('system', 'System'),
    ]
    
    # Core fields
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='low', db_index=True)
    module = models.CharField(max_length=20, choices=MODULES, db_index=True)
    
    # Description and details
    description = models.CharField(max_length=500, help_text="Brief description of the action")
    details = models.TextField(blank=True, help_text="Detailed information about the action")
    
    # Object tracking (generic foreign key)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    
    # Session and request tracking
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    request_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    
    # Change tracking (for updates)
    old_values = models.JSONField(null=True, blank=True, help_text="Previous values before update")
    new_values = models.JSONField(null=True, blank=True, help_text="New values after update")
    
    # Additional metadata
    metadata = models.JSONField(null=True, blank=True, help_text="Additional context data")
    
    # Status and outcome
    success = models.BooleanField(default=True, help_text="Was the action successful?")
    error_message = models.TextField(blank=True, help_text="Error details if action failed")
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'module']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        user_info = f"{self.user.get_full_name()}" if self.user else "System"
        return f"{user_info} - {self.get_action_display()} - {self.description} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

    def get_absolute_url(self):
        return reverse('audit:audit_detail', kwargs={'pk': self.pk})

    @property
    def object_repr(self):
        """Get string representation of the related object"""
        if self.content_object:
            return str(self.content_object)
        return self.object_id or "N/A"

    @property
    def object_type(self):
        """Get the type of the related object"""
        if self.content_type:
            return self.content_type.model_class().__name__
        return "Unknown"

    @property
    def changes_summary(self):
        """Get a summary of changes made"""
        if self.action != 'update' or not self.old_values or not self.new_values:
            return None
        
        changes = []
        for field in self.new_values:
            if field in self.old_values:
                old_val = self.old_values[field]
                new_val = self.new_values[field]
                if old_val != new_val:
                    changes.append(f"{field}: {old_val} → {new_val}")
        
        return ", ".join(changes) if changes else None

    @classmethod
    def log_action(cls, user, action, description, module='system', severity='low', 
                   content_object=None, details='', ip_address=None, user_agent='',
                   old_values=None, new_values=None, metadata=None, success=True,
                   error_message='', session_key=None, request_id=None):
        """Create an audit log entry"""
        content_type = None
        object_id = None
        
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = str(content_object.pk)
        
        return cls.objects.create(
            user=user,
            action=action,
            description=description,
            module=module,
            severity=severity,
            content_type=content_type,
            object_id=object_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
            success=success,
            error_message=error_message,
            session_key=session_key,
            request_id=request_id,
        )

    @classmethod
    def log_login(cls, user, success=True, ip_address=None, user_agent='', error_message=''):
        """Log login attempts"""
        action = 'login' if success else 'login_failed'
        severity = 'low' if success else 'medium'
        description = f"Login {'successful' if success else 'failed'}"
        
        if not success and user:
            description += f" for {user.get_full_name()}"
        
        return cls.log_action(
            user=user if success else None,
            action=action,
            description=description,
            module='accounts',
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )

    @classmethod
    def log_logout(cls, user, ip_address=None, user_agent=''):
        """Log logout events"""
        return cls.log_action(
            user=user,
            action='logout',
            description="User logged out",
            module='accounts',
            severity='low',
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def log_crud(cls, user, action, instance, description='', details='', old_values=None, new_values=None, 
                 ip_address=None, user_agent='', severity='low'):
        """Log Create, Read, Update, Delete operations"""
        if not description:
            action_desc = {
                'create': 'created',
                'update': 'updated',
                'delete': 'deleted',
                'view': 'viewed'
            }.get(action, action)
            
            model_name = instance.__class__.__name__
            description = f"{model_name} {action_desc}"
            if hasattr(instance, 'title'):
                description += f": {instance.title}"
            elif hasattr(instance, 'name'):
                description += f": {instance.name}"
        
        # Determine module from model
        module_map = {
            'User': 'accounts',
            'Meeting': 'meetings',
            'Document': 'documents',
            'Motion': 'voting',
            'Risk': 'risk',
            'Policy': 'policy',
            'AuditLog': 'audit',
        }
        module = module_map.get(instance.__class__.__name__, 'system')
        
        return cls.log_action(
            user=user,
            action=action,
            description=description,
            module=module,
            content_object=instance,
            details=details,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
        )

class AuditLogExport(models.Model):
    """Track audit log export requests"""
    
    EXPORT_FORMATS = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('pdf', 'PDF'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Export parameters
    format = models.CharField(max_length=10, choices=EXPORT_FORMATS)
    filters = models.JSONField(null=True, blank=True, help_text="Applied filters for the export")
    
    # Results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=500, blank=True)
    record_count = models.IntegerField(null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name_plural = "Audit Log Exports"

    def __str__(self):
        return f"Export {self.pk} - {self.get_format_display()} - {self.get_status_display()}"

class AuditLogRetention(models.Model):
    """Configure audit log retention policies"""
    
    MODULE_CHOICES = [
        ('all', 'All Modules'),
        ('accounts', 'Accounts'),
        ('meetings', 'Meetings'),
        ('documents', 'Documents'),
        ('voting', 'Voting'),
        ('risk', 'Risk Management'),
        ('policy', 'Policies'),
        ('audit', 'Audit Trail'),
        ('evaluation', 'Board Evaluation'),
        ('discussions', 'Discussions'),
        ('system', 'System'),
    ]
    
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, unique=True)
    retention_days = models.IntegerField(help_text="Number of days to retain logs for this module")
    archive_after_days = models.IntegerField(null=True, blank=True, help_text="Archive logs after this many days (optional)")
    
    # Auto-cleanup settings
    auto_cleanup = models.BooleanField(default=True, help_text="Automatically cleanup old logs")
    last_cleanup = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['module']
        verbose_name_plural = "Audit Log Retention Policies"

    def __str__(self):
        return f"{self.get_module_display()} - {self.retention_days} days"
