from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import mimetypes
try:
    import magic
except ImportError:
    magic = None
from .models import (
    Document, DocumentCategory, DocumentAccess, DocumentComment, DocumentTag, 
    DocumentShare, DocumentWorkflow, DocumentVersion, DocumentTagging
)
from apps.accounts.models import User

class DocumentUploadForm(forms.ModelForm):
    """Enhanced form for uploading documents with version control"""
    
    create_version = forms.BooleanField(
        required=False,
        help_text="Create as new version of existing document with same title"
    )
    change_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Describe changes in this version...'
        })
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=DocumentTag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    collaborators = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role='board_member'),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    is_collaborative = forms.BooleanField(
        required=False,
        help_text="Allow multiple users to collaborate on this document"
    )
    
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'category', 'file', 
            'access_level', 'status', 'is_collaborative'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Document title'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Document description'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DocumentCategory.objects.all()
    
    def clean_file(self):
        """Validate file upload with automatic type detection"""
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (100MB limit increased)
            if file.size > 100 * 1024 * 1024:
                raise ValidationError(_('File size cannot exceed 100MB.'))
            
            # Automatic file type detection using python-magic
            try:
                if magic is None:
                    raise ImportError("python-magic is not installed")
                # Read first 1024 bytes for mime detection
                file_content = file.read(1024)
                file.seek(0)  # Reset file pointer
                
                # Detect mime type
                detected_mime = magic.from_buffer(file_content, mime=True)
                
                # Get file extension from filename
                filename = file.name.lower()
                extension = filename.split('.')[-1] if '.' in filename else ''
                
                # Comprehensive allowed file types
                allowed_mime_types = {
                    # Documents
                    'application/pdf': ['pdf'],
                    'application/msword': ['doc'],
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
                    'application/vnd.ms-excel': ['xls'],
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
                    'application/vnd.ms-powerpoint': ['ppt'],
                    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx'],
                    'text/plain': ['txt'],
                    'text/rtf': ['rtf'],
                    
                    # Images
                    'image/jpeg': ['jpg', 'jpeg'],
                    'image/png': ['png'],
                    'image/gif': ['gif'],
                    'image/bmp': ['bmp'],
                    'image/tiff': ['tiff', 'tif'],
                    'image/webp': ['webp'],
                    
                    # Archives
                    'application/zip': ['zip'],
                    'application/x-rar-compressed': ['rar'],
                    'application/x-7z-compressed': ['7z'],
                    
                    # Other common types
                    'application/json': ['json'],
                    'application/xml': ['xml'],
                    'text/csv': ['csv'],
                    'text/html': ['html', 'htm'],
                }
                
                # Check if detected mime type is allowed
                if detected_mime not in allowed_mime_types:
                    # Try to map extension to mime type for additional validation
                    expected_mime = mimetypes.guess_type(filename)[0]
                    if expected_mime != detected_mime:
                        raise ValidationError(_(
                            f'File type detection failed. Detected: {detected_mime}, '
                            f'Expected from filename: {expected_mime}. '
                            f'Please ensure the file is not corrupted.'
                        ))
                    elif expected_mime not in allowed_mime_types:
                        raise ValidationError(_(
                            f'File type "{detected_mime}" is not allowed. '
                            f'Allowed types: PDF, Word, Excel, PowerPoint, images, archives, etc.'
                        ))
                
                # Additional validation for specific extensions
                if extension in allowed_mime_types.get(detected_mime, []):
                    pass  # Valid
                else:
                    raise ValidationError(_(
                        f'File extension ".{extension}" does not match detected file type "{detected_mime}".'
                    ))
                
                # Store detected information for later use
                self.detected_mime_type = detected_mime
                self.detected_extension = extension
                
            except ImportError:
                # Fallback if python-magic is not available
                allowed_extensions = [
                    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 
                    'txt', 'rtf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 
                    'tiff', 'tif', 'webp', 'zip', 'rar', '7z', 'json', 
                    'xml', 'csv', 'html', 'htm'
                ]
                file_extension = file.name.split('.')[-1].lower()
                if file_extension not in allowed_extensions:
                    raise ValidationError(_(
                        f'File type .{file_extension} is not allowed. '
                        f'Allowed types: {", ".join(allowed_extensions)}'
                    ))
        
        return file
    
    def save(self, commit=True):
        document = super().save(commit=False)
        
        if commit:
            document.save()
            
            # Save tags
            if self.cleaned_data.get('tags'):
                for tag in self.cleaned_data['tags']:
                    DocumentTagging.objects.create(
                        document=document,
                        tag=tag,
                        created_by=document.uploaded_by
                    )
                    # Update tag usage count
                    tag.usage_count += 1
                    tag.save()
            
            # Save collaborators
            if self.cleaned_data.get('collaborators'):
                document.collaborators.set(self.cleaned_data['collaborators'])
        
        return document

class DocumentCommentForm(forms.ModelForm):
    """Form for adding comments to documents"""
    
    class Meta:
        model = DocumentComment
        fields = ['content', 'page_number', 'section_reference']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Add your comment...'
            }),
            'page_number': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Page number (optional)'
            }),
            'section_reference': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Section reference (optional)'
            }),
        }

class DocumentTagForm(forms.ModelForm):
    """Form for creating document tags"""
    
    class Meta:
        model = DocumentTag
        fields = ['name', 'color', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Tag name'
            }),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'w-full h-10 px-2 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Tag description (optional)'
            }),
        }

class DocumentShareForm(forms.ModelForm):
    """Form for creating document share links"""
    
    class Meta:
        model = DocumentShare
        fields = ['can_download', 'can_comment', 'can_edit', 'expires_at', 'max_downloads']
        widgets = {
            'expires_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'max_downloads': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Maximum downloads (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add checkboxes with proper styling
        self.fields['can_download'].widget = forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })
        self.fields['can_comment'].widget = forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })
        self.fields['can_edit'].widget = forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })

class DocumentWorkflowForm(forms.ModelForm):
    """Form for managing document workflows"""
    
    class Meta:
        model = DocumentWorkflow
        fields = ['current_stage', 'assigned_to', 'action_required', 'deadline']
        widgets = {
            'current_stage': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'action_required': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Action required'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(role__in=['company_secretary', 'it_administrator', 'board_member'])

class DocumentSearchForm(forms.Form):
    """Enhanced search form for documents"""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Search documents...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=DocumentCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Document.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    access_level = forms.ChoiceField(
        choices=[('', 'All Access Levels')] + Document.ACCESS_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    tags = forms.ModelMultipleChoiceField(
        queryset=DocumentTag.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    uploaded_by = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=['company_secretary', 'it_administrator', 'board_member']),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
        })
    )

class CategoryForm(forms.ModelForm):
    """Form for document categories"""
    
    class Meta:
        model = DocumentCategory
        fields = ['name', 'description', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Category name'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent',
                'placeholder': 'Category description'
            }),
            'parent': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude self from parent choices to prevent circular references
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = DocumentCategory.objects.exclude(pk=self.instance.pk)

class DocumentAccessForm(forms.ModelForm):
    """Form for managing document access permissions"""
    
    class Meta:
        model = DocumentAccess
        fields = ['user', 'permission', 'expires_at']
        widgets = {
            'user': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'permission': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.all()
