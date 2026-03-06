import uuid
import os
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.postgres.search import SearchVector, SearchRank
from django.contrib.postgres.indexes import GinIndex
from apps.accounts.models import User

class DocumentCategory(models.Model):
    """Document categories for organization"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    # Permissions
    can_upload = models.ManyToManyField(User, related_name='uploadable_categories', blank=True)
    can_view = models.ManyToManyField(User, related_name='viewable_categories', blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Document Category'
        verbose_name_plural = 'Document Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def full_path(self):
        """Get full category path including parent categories"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

class Document(models.Model):
    """Main document model with file upload and metadata"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    ACCESS_LEVEL_CHOICES = [
        ('public', 'Public'),
        ('board', 'Board Members Only'),
        ('committee', 'Committee Members Only'),
        ('restricted', 'Restricted Access'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, related_name='documents')
    
    # File information
    file = models.FileField(upload_to='documents/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100)
    mime_type = models.CharField(max_length=100)
    
    # Status and access
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='board')
    
    # Version control
    version = models.PositiveIntegerField(default=1)
    is_latest_version = models.BooleanField(default=True)
    
    # Search and indexing (handled via database triggers and queries)
    
    # Collaboration
    is_collaborative = models.BooleanField(default=False)
    collaborators = models.ManyToManyField(User, related_name='collaborative_documents', blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['status']),
            models.Index(fields=['access_level']),
            models.Index(fields=['uploaded_by', '-created_at']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def file_extension(self):
        """Get file extension"""
        return os.path.splitext(self.file_name)[1].lower()
    
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
    
    def get_absolute_url(self):
        """Get absolute URL for document"""
        return f"/documents/{self.id}/"
    
    def save(self, *args, **kwargs):
        """Set file metadata before saving with enhanced type detection"""
        if self.file:
            # Set basic file information
            self.file_name = self.file.name
            self.file_size = self.file.size
            
            # Enhanced file type detection
            try:
                import magic
                # Read first 1024 bytes for mime detection
                file_content = self.file.read(1024)
                self.file.seek(0)  # Reset file pointer
                
                # Detect mime type
                detected_mime = magic.from_buffer(file_content, mime=True)
                self.mime_type = detected_mime
                
                # Determine file type category from mime type
                if detected_mime.startswith('application/pdf'):
                    self.file_type = 'PDF'
                elif detected_mime.startswith('application/msword') or detected_mime.startswith('application/vnd.openxmlformats-officedocument.wordprocessingml'):
                    self.file_type = 'Word Document'
                elif detected_mime.startswith('application/vnd.ms-excel') or detected_mime.startswith('application/vnd.openxmlformats-officedocument.spreadsheetml'):
                    self.file_type = 'Excel Spreadsheet'
                elif detected_mime.startswith('application/vnd.ms-powerpoint') or detected_mime.startswith('application/vnd.openxmlformats-officedocument.presentationml'):
                    self.file_type = 'PowerPoint Presentation'
                elif detected_mime.startswith('text/'):
                    self.file_type = 'Text Document'
                elif detected_mime.startswith('image/'):
                    self.file_type = 'Image'
                elif detected_mime.startswith('application/zip') or detected_mime.startswith('application/x-rar'):
                    self.file_type = 'Archive'
                else:
                    self.file_type = 'Other'
                    
            except ImportError:
                # Fallback to basic detection
                self.mime_type = getattr(self.file, 'content_type', 'application/octet-stream')
                file_extension = os.path.splitext(self.file.name)[1].lower()
                
                # Map extension to file type
                extension_map = {
                    '.pdf': 'PDF',
                    '.doc': 'Word Document',
                    '.docx': 'Word Document',
                    '.xls': 'Excel Spreadsheet',
                    '.xlsx': 'Excel Spreadsheet',
                    '.ppt': 'PowerPoint Presentation',
                    '.pptx': 'PowerPoint Presentation',
                    '.txt': 'Text Document',
                    '.rtf': 'Text Document',
                    '.jpg': 'Image',
                    '.jpeg': 'Image',
                    '.png': 'Image',
                    '.gif': 'Image',
                    '.bmp': 'Image',
                    '.tiff': 'Image',
                    '.webp': 'Image',
                    '.zip': 'Archive',
                    '.rar': 'Archive',
                    '.7z': 'Archive',
                }
                self.file_type = extension_map.get(file_extension, 'Other')
        
        super().save(*args, **kwargs)

class DocumentVersion(models.Model):
    """Document version control with enhanced tracking"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    file = models.FileField(upload_to='documents/versions/%Y/%m/')
    change_notes = models.TextField(blank=True, help_text="Notes about changes in this version")
    
    # Version metadata
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    checksum = models.CharField(max_length=64, blank=True, help_text="SHA-256 checksum for integrity")
    is_major_version = models.BooleanField(default=False)
    
    # Collaboration tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='document_versions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Approval workflow
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_versions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Document Version'
        verbose_name_plural = 'Document Versions'
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']
        indexes = [
            models.Index(fields=['document', '-version_number']),
            models.Index(fields=['created_by', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.document.title} v{self.version_number}"
    
    def save(self, *args, **kwargs):
        """Set file metadata and checksum before saving"""
        if self.file:
            self.file_size = self.file.size
            # Generate checksum
            import hashlib
            hasher = hashlib.sha256()
            for chunk in self.file.chunks():
                hasher.update(chunk)
            self.checksum = hasher.hexdigest()
        super().save(*args, **kwargs)

class DocumentAccess(models.Model):
    """Document access permissions and tracking"""
    
    PERMISSION_CHOICES = [
        ('view', 'Can View'),
        ('download', 'Can Download'),
        ('edit', 'Can Edit'),
        ('delete', 'Can Delete'),
        ('share', 'Can Share'),
        ('comment', 'Can Comment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_records')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_access')
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES)
    
    # Access tracking
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Document Access'
        verbose_name_plural = 'Document Access'
        unique_together = ['document', 'user', 'permission']
        indexes = [
            models.Index(fields=['document', 'user']),
            models.Index(fields=['user', 'permission']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_permission_display()} - {self.document.title}"
    
    @property
    def is_expired(self):
        """Check if access has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

class DocumentActivity(models.Model):
    """Track document activity and access"""
    
    ACTIVITY_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('edited', 'Edited'),
        ('deleted', 'Deleted'),
        ('permission_granted', 'Permission Granted'),
        ('permission_revoked', 'Permission Revoked'),
        ('version_created', 'Version Created'),
        ('comment_added', 'Comment Added'),
        ('shared', 'Shared'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Related object (for version tracking, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Document Activity'
        verbose_name_plural = 'Document Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['activity_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_activity_type_display()} - {self.document.title}"

class DocumentComment(models.Model):
    """Document comments for collaboration"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_comments')
    
    # Comment content
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Position in document (for page/section references)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section_reference = models.CharField(max_length=200, blank=True)
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='resolved_comments')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Document Comment'
        verbose_name_plural = 'Document Comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.get_full_name()} on {self.document.title}"

class DocumentTag(models.Model):
    """Document tags for categorization and search"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code")
    description = models.TextField(blank=True)
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Document Tag'
        verbose_name_plural = 'Document Tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class DocumentTagging(models.Model):
    """Many-to-many relationship between documents and tags"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='taggings')
    tag = models.ForeignKey(DocumentTag, on_delete=models.CASCADE, related_name='document_taggings')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='document_taggings')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Document Tagging'
        verbose_name_plural = 'Document Taggings'
        unique_together = ['document', 'tag']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['tag']),
        ]
    
    def __str__(self):
        return f"{self.document.title} - {self.tag.name}"

class DocumentShare(models.Model):
    """Document sharing links and permissions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='shares')
    
    # Share details
    share_token = models.UUIDField(unique=True, default=uuid.uuid4)
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_documents')
    
    # Permissions
    can_download = models.BooleanField(default=True)
    can_comment = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    
    # Access control
    expires_at = models.DateTimeField(null=True, blank=True)
    max_downloads = models.PositiveIntegerField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Document Share'
        verbose_name_plural = 'Document Shares'
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['document', '-created_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Share link for {self.document.title}"
    
    @property
    def is_expired(self):
        """Check if share has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        if self.max_downloads and self.download_count >= self.max_downloads:
            return True
        return False
    
    @property
    def share_url(self):
        """Get share URL"""
        return f"/documents/share/{self.share_token}/"

class DocumentWorkflow(models.Model):
    """Document approval workflow"""
    
    WORKFLOW_STAGES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='workflows')
    
    # Workflow details
    current_stage = models.CharField(max_length=20, choices=WORKFLOW_STAGES, default='draft')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_workflows')
    
    # Actions
    action_required = models.CharField(max_length=200, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_workflows')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Document Workflow'
        verbose_name_plural = 'Document Workflows'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document', '-created_at']),
            models.Index(fields=['assigned_to', '-created_at']),
            models.Index(fields=['current_stage']),
        ]
    
    def __str__(self):
        return f"Workflow for {self.document.title} - {self.get_current_stage_display()}"

class DocumentWorkflowAction(models.Model):
    """Workflow action history"""
    
    ACTION_TYPES = [
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned for Review'),
        ('escalated', 'Escalated'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(DocumentWorkflow, on_delete=models.CASCADE, related_name='actions')
    
    # Action details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflow_actions')
    comments = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Workflow Action'
        verbose_name_plural = 'Workflow Actions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow', '-created_at']),
            models.Index(fields=['actor', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.actor.get_full_name()} - {self.get_action_type_display()} - {self.workflow.document.title}"
