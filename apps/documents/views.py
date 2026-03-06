from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, Count, F
from django.http import HttpResponse, Http404, JsonResponse
from django.core.files.storage import default_storage
from django.contrib.postgres.search import SearchVector, SearchRank, SearchQuery
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator

from apps.accounts.models import User

from .models import (
    Document, DocumentCategory, DocumentAccess, DocumentActivity, DocumentVersion,
    DocumentComment, DocumentTag, DocumentTagging, DocumentShare, DocumentWorkflow,
    DocumentWorkflowAction
)
from .forms import (
    DocumentUploadForm, CategoryForm, DocumentSearchForm, DocumentAccessForm,
    DocumentCommentForm, DocumentTagForm, DocumentShareForm, DocumentWorkflowForm
)
from apps.accounts.decorators import role_required
from apps.accounts.permissions import MANAGE_DOCUMENTS
from apps.notifications.views import create_notification

class DocumentListView(LoginRequiredMixin, ListView):
    """Enhanced list view for documents with advanced search and filtering"""
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 12
    
    def get_queryset(self):
        """Filter documents based on user role, permissions, and search"""
        user = self.request.user
        queryset = Document.objects.select_related('uploaded_by', 'category').prefetch_related('taggings__tag')
        
        # Base role-based filtering
        if user.role == 'it_administrator':
            # IT admins see all documents
            base_queryset = queryset
        elif user.role == 'company_secretary':
            # Company secretaries see all published and approved documents
            base_queryset = queryset.filter(status__in=['published', 'approved'])
        elif user.role == 'board_member':
            # Board members see board-level documents
            base_queryset = queryset.filter(access_level__in=['public', 'board'], status='published')
        else:
            # Other roles see documents they have explicit access to
            accessible_docs = DocumentAccess.objects.filter(
                user=user, 
                permission='view',
                expires_at__gt=timezone.now()
            ).values_list('document_id', flat=True)
            base_queryset = queryset.filter(
                id__in=accessible_docs,
                status='published'
            )
        
        # Apply search filters
        search_query = self.request.GET.get('search')
        if search_query:
            base_queryset = base_queryset.annotate(
                rank=SearchRank(SearchVector('title', 'description'), SearchQuery(search_query))
            ).filter(search_vector=SearchQuery(search_query)).order_by('-rank')
        
        # Apply other filters
        category = self.request.GET.get('category')
        if category:
            base_queryset = base_queryset.filter(category_id=category)
        
        status = self.request.GET.get('status')
        if status:
            base_queryset = base_queryset.filter(status=status)
        
        access_level = self.request.GET.get('access_level')
        if access_level:
            base_queryset = base_queryset.filter(access_level=access_level)
        
        tags = self.request.GET.getlist('tags')
        if tags:
            base_queryset = base_queryset.filter(taggings__tag_id__in=tags).distinct()
        
        uploaded_by = self.request.GET.get('uploaded_by')
        if uploaded_by:
            base_queryset = base_queryset.filter(uploaded_by_id=uploaded_by)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            base_queryset = base_queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            base_queryset = base_queryset.filter(created_at__date__lte=date_to)
        
        return base_queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DocumentSearchForm(self.request.GET)
        context['categories'] = DocumentCategory.objects.all()
        context['tags'] = DocumentTag.objects.all().order_by('-usage_count')
        context['users'] = User.objects.filter(role__in=['company_secretary', 'it_administrator', 'board_member'])
        
        # Set can_manage based on user permissions
        user = self.request.user
        context['can_manage'] = user.role in ['it_administrator', 'company_secretary'] or DocumentAccess.objects.filter(
            user=user, 
            permission='edit',
            expires_at__gt=timezone.now()
        ).exists()
        
        return context

class DocumentDetailView(LoginRequiredMixin, DetailView):
    """Enhanced document detail view with version control and collaboration"""
    model = Document
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'
    
    def get_queryset(self):
        """Filter documents based on user permissions"""
        user = self.request.user
        queryset = Document.objects.select_related('uploaded_by', 'category').prefetch_related(
            'versions', 'comments', 'taggings__tag', 'shares', 'activities'
        )
        
        # Apply same role-based filtering as list view
        if user.role == 'it_administrator':
            return queryset
        elif user.role == 'company_secretary':
            return queryset.filter(status__in=['published', 'approved'])
        elif user.role == 'board_member':
            return queryset.filter(access_level__in=['public', 'board'], status='published')
        else:
            accessible_docs = DocumentAccess.objects.filter(
                user=user, 
                permission='view',
                expires_at__gt=timezone.now()
            ).values_list('document_id', flat=True)
            return queryset.filter(id__in=accessible_docs, status='published')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.object
        user = self.request.user
        
        # Get versions
        context['versions'] = document.versions.order_by('-version_number')
        
        # Get comments
        context['comments'] = document.comments.filter(parent=None).order_by('-created_at')
        
        # Get tags
        context['tags'] = [tagging.tag for tagging in document.taggings.all()]
        
        # Get shares
        context['shares'] = document.shares.filter(expires_at__gt=timezone.now())
        
        # Get recent activities
        context['recent_activities'] = document.activities.order_by('-created_at')[:10]
        
        # Check user permissions
        context['can_edit'] = self.can_edit_document(document, user)
        context['can_download'] = self.can_download_document(document, user)
        context['can_share'] = self.can_share_document(document, user)
        context['can_comment'] = self.can_comment_document(document, user)
        
        # Add forms
        context['comment_form'] = DocumentCommentForm()
        context['share_form'] = DocumentShareForm()
        
        # Track view activity
        self.track_activity(document, user, 'viewed')
        
        return context
    
    def can_edit_document(self, document, user):
        """Check if user can edit document"""
        if user.role in ['it_administrator', 'company_secretary']:
            return True
        if document.uploaded_by == user:
            return True
        if document.is_collaborative and user in document.collaborators.all():
            return True
        return DocumentAccess.objects.filter(
            document=document, user=user, permission='edit',
            expires_at__gt=timezone.now()
        ).exists()
    
    def can_download_document(self, document, user):
        """Check if user can download document"""
        if user.role in ['it_administrator', 'company_secretary']:
            return True
        if document.uploaded_by == user:
            return True
        if document.is_collaborative and user in document.collaborators.all():
            return True
        return DocumentAccess.objects.filter(
            document=document, user=user, permission='download',
            expires_at__gt=timezone.now()
        ).exists()
    
    def can_share_document(self, document, user):
        """Check if user can share document"""
        if user.role in ['it_administrator', 'company_secretary']:
            return True
        if document.uploaded_by == user:
            return True
        return DocumentAccess.objects.filter(
            document=document, user=user, permission='share',
            expires_at__gt=timezone.now()
        ).exists()
    
    def can_comment_document(self, document, user):
        """Check if user can comment on document"""
        if user.role in ['it_administrator', 'company_secretary']:
            return True
        if document.uploaded_by == user:
            return True
        if document.is_collaborative and user in document.collaborators.all():
            return True
        return DocumentAccess.objects.filter(
            document=document, user=user, permission='comment',
            expires_at__gt=timezone.now()
        ).exists()
    
    def track_activity(self, document, user, activity_type):
        """Track document activity"""
        DocumentActivity.objects.create(
            document=document,
            user=user,
            activity_type=activity_type,
            ip_address=self.get_client_ip(self.request)
        )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class DocumentUploadView(LoginRequiredMixin, CreateView):
    """Enhanced document upload with version control"""
    model = Document
    form_class = DocumentUploadForm
    template_name = 'documents/document_upload.html'
    success_url = reverse_lazy('documents:document_list')
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        
        # Check if this is a new version of an existing document
        existing_doc = Document.objects.filter(
            title=form.cleaned_data['title'],
            uploaded_by=self.request.user
        ).first()
        
        if existing_doc and form.cleaned_data.get('create_version'):
            # Create new version
            version_number = existing_doc.versions.count() + 1
            existing_doc.version = version_number
            existing_doc.file = form.cleaned_data['file']
            existing_doc.save()
            
            # Create version record
            DocumentVersion.objects.create(
                document=existing_doc,
                version_number=version_number,
                file=form.cleaned_data['file'],
                change_notes=form.cleaned_data.get('change_notes', ''),
                created_by=self.request.user
            )
            
            # Track activity
            DocumentActivity.objects.create(
                document=existing_doc,
                user=self.request.user,
                activity_type='version_created',
                description=f"Created version {version_number}",
                ip_address=self.get_client_ip(self.request)
            )
            
            messages.success(self.request, f"New version of '{existing_doc.title}' uploaded successfully.")
        else:
            # Create new document
            response = super().form_valid(form)
            
            # Track activity
            DocumentActivity.objects.create(
                document=self.object,
                user=self.request.user,
                activity_type='uploaded',
                description=f"Uploaded document '{self.object.title}'",
                ip_address=self.get_client_ip(self.request)
            )
            
            # Send notification to relevant users
            self.send_document_notification(self.object)
            
            return response
        
        return redirect('documents:document_list')
    
    def send_document_notification(self, document):
        """Send notification about new document"""
        # Notify board members about new documents
        from apps.accounts.models import User
        board_members = User.objects.filter(role='board_member')
        
        for member in board_members:
            create_notification(
                recipient=member,
                title=f"New Document: {document.title}",
                message=f"A new document '{document.title}' has been uploaded by {self.request.user.get_full_name()}.",
                notification_type='document_shared',
                priority='normal',
                action_url=document.get_absolute_url(),
                metadata={'document_id': str(document.id)}
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

@login_required
def document_download(request, pk):
    """Download document with access tracking"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check download permissions
    view = DocumentDetailView()
    if not view.can_download_document(document, user):
        messages.error(request, "You don't have permission to download this document.")
        return redirect('documents:document_detail', pk=pk)
    
    # Track download activity
    DocumentActivity.objects.create(
        document=document,
        user=user,
        activity_type='downloaded',
        ip_address=view.get_client_ip(request)
    )
    
    # Serve file
    if document.file and default_storage.exists(document.file.name):
        response = HttpResponse(default_storage.open(document.file.name, 'rb').read())
        response['Content-Type'] = document.mime_type
        response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
        return response
    
    raise Http404("File not found")

@login_required
@require_POST
def add_comment(request, pk):
    """Add comment to document"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check comment permissions
    view = DocumentDetailView()
    if not view.can_comment_document(document, user):
        messages.error(request, "You don't have permission to comment on this document.")
        return redirect('documents:document_detail', pk=pk)
    
    form = DocumentCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.document = document
        comment.user = user
        comment.save()
        
        # Track activity
        DocumentActivity.objects.create(
            document=document,
            user=user,
            activity_type='comment_added',
            description=f"Added comment: {comment.content[:50]}...",
            ip_address=view.get_client_ip(request)
        )
        
        # Send notification to document owner and collaborators
        if document.uploaded_by != user:
            create_notification(
                recipient=document.uploaded_by,
                title=f"New Comment on {document.title}",
                message=f"{user.get_full_name()} commented on your document '{document.title}'.",
                notification_type='discussion_reply',
                priority='normal',
                action_url=document.get_absolute_url(),
                metadata={'document_id': str(document.id), 'comment_id': str(comment.id)}
            )
        
        messages.success(request, "Comment added successfully.")
    else:
        messages.error(request, "Error adding comment.")
    
    return redirect('documents:document_detail', pk=pk)

@login_required
@require_POST
def share_document(request, pk):
    """Create share link for document"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check share permissions
    view = DocumentDetailView()
    if not view.can_share_document(document, user):
        messages.error(request, "You don't have permission to share this document.")
        return redirect('documents:document_detail', pk=pk)
    
    form = DocumentShareForm(request.POST)
    if form.is_valid():
        share = form.save(commit=False)
        share.document = document
        share.shared_by = user
        share.save()
        
        # Track activity
        DocumentActivity.objects.create(
            document=document,
            user=user,
            activity_type='shared',
            description=f"Created share link with permissions: {form.cleaned_data.get('permissions', 'view')}",
            ip_address=view.get_client_ip(request)
        )
        
        messages.success(request, f"Share link created: {share.share_url}")
    else:
        messages.error(request, "Error creating share link.")
    
    return redirect('documents:document_detail', pk=pk)

@login_required
def shared_document(request, token):
    """Access shared document via share link"""
    try:
        share = DocumentShare.objects.get(share_token=token)
    except DocumentShare.DoesNotExist:
        raise Http404("Share link not found.")
    
    # Check if share is valid
    if share.is_expired:
        raise Http404("Share link has expired.")
    
    # Update last accessed
    share.last_accessed = timezone.now()
    share.save(update_fields=['last_accessed'])
    
    # Track access
    DocumentActivity.objects.create(
        document=share.document,
        user=request.user if request.user.is_authenticated else None,
        activity_type='viewed',
        description=f"Accessed via share link",
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return render(request, 'documents/shared_document.html', {
        'document': share.document,
        'share': share
    })

@login_required
def document_search(request):
    """Advanced document search with full-text search"""
    query = request.GET.get('q', '')
    category = request.GET.get('category')
    tags = request.GET.getlist('tags')
    
    documents = Document.objects.select_related('uploaded_by', 'category').prefetch_related('taggings__tag')
    
    # Apply search
    if query:
        documents = documents.annotate(
            rank=SearchRank(SearchVector('title', 'description'), SearchQuery(query))
        ).filter(search_vector=SearchQuery(query)).order_by('-rank')
    
    # Apply filters
    if category:
        documents = documents.filter(category_id=category)
    
    if tags:
        documents = documents.filter(taggings__tag_id__in=tags).distinct()
    
    # Apply user permissions
    user = request.user
    if user.role == 'it_administrator':
        pass  # See all
    elif user.role == 'company_secretary':
        documents = documents.filter(status__in=['published', 'approved'])
    elif user.role == 'board_member':
        documents = documents.filter(access_level__in=['public', 'board'], status='published')
    else:
        accessible_docs = DocumentAccess.objects.filter(
            user=user, 
            permission='view',
            expires_at__gt=timezone.now()
        ).values_list('document_id', flat=True)
        documents = documents.filter(id__in=accessible_docs, status='published')
    
    documents = documents.order_by('-created_at')
    
    return render(request, 'documents/search_results.html', {
        'documents': documents,
        'query': query,
        'categories': DocumentCategory.objects.all(),
        'tags': DocumentTag.objects.all(),
        'selected_category': category,
        'selected_tags': tags
    })

@login_required
def document_versions(request, pk):
    """View document version history"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check view permissions
    view = DocumentDetailView()
    if not view.can_download_document(document, user):
        messages.error(request, "You don't have permission to view this document.")
        return redirect('documents:document_detail', pk=pk)
    
    versions = document.versions.order_by('-version_number')
    
    return render(request, 'documents/versions.html', {
        'document': document,
        'versions': versions
    })

@login_required
def download_version(request, pk, version_number):
    """Download specific document version"""
    document = get_object_or_404(Document, pk=pk)
    version = get_object_or_404(DocumentVersion, document=document, version_number=version_number)
    user = request.user
    
    # Check download permissions
    view = DocumentDetailView()
    if not view.can_download_document(document, user):
        messages.error(request, "You don't have permission to download this document.")
        return redirect('documents:document_detail', pk=pk)
    
    # Serve version file
    if version.file and default_storage.exists(version.file.name):
        response = HttpResponse(default_storage.open(version.file.name, 'rb').read())
        response['Content-Type'] = document.mime_type
        response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
        return response
    
    raise Http404("Version file not found")

# Workflow views
@login_required
def document_workflow(request, pk):
    """View and manage document workflow"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check permissions
    if user.role not in ['it_administrator', 'company_secretary']:
        if document.uploaded_by != user:
            messages.error(request, "You don't have permission to manage workflows.")
            return redirect('documents:document_detail', pk=pk)
    
    workflow, created = DocumentWorkflow.objects.get_or_create(
        document=document,
        defaults={'created_by': user}
    )
    
    if request.method == 'POST':
        form = DocumentWorkflowForm(request.POST, instance=workflow)
        if form.is_valid():
            form.save()
            
            # Track workflow action
            DocumentWorkflowAction.objects.create(
                workflow=workflow,
                action_type='submitted',
                actor=user,
                comments=form.cleaned_data.get('comments', '')
            )
            
            messages.success(request, "Workflow updated successfully.")
            return redirect('documents:document_detail', pk=pk)
    else:
        form = DocumentWorkflowForm(instance=workflow)
    
    return render(request, 'documents/workflow.html', {
        'document': document,
        'workflow': workflow,
        'form': form,
        'actions': workflow.actions.order_by('-created_at')
    })

# Tag management views
@login_required
def manage_tags(request):
    """Manage document tags"""
    if request.user.role not in ['it_administrator', 'company_secretary']:
        messages.error(request, "You don't have permission to manage tags.")
        return redirect('documents:document_list')
    
    tags = DocumentTag.objects.annotate(usage_count=Count('document_taggings')).order_by('-usage_count')
    
    if request.method == 'POST':
        form = DocumentTagForm(request.POST)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.created_by = request.user
            tag.save()
            messages.success(request, f"Tag '{tag.name}' created successfully.")
            return redirect('documents:manage_tags')
    else:
        form = DocumentTagForm()
    
    return render(request, 'documents/manage_tags.html', {
        'tags': tags,
        'form': form
    })
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DocumentSearchForm(self.request.GET or None)
        context['can_manage'] = self.request.user.role in MANAGE_DOCUMENTS
        return context

class DocumentDetailView(LoginRequiredMixin, DetailView):
    """Detail view for individual documents"""
    model = Document
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'
    
    def get_object(self):
        """Get document with access check"""
        document = super().get_object()
        user = self.request.user
        
        # Check access permissions
        if not self.has_access(user, document):
            raise Http404("You don't have permission to view this document")
        
        return document
    
    def has_access(self, user, document):
        """Check if user has access to document"""
        # IT admins have access to all
        if user.role == 'it_administrator':
            return True
        
        # Company secretaries can see published/approved documents
        if user.role == 'company_secretary' and document.status in ['published', 'approved']:
            return True
        
        # Board members can see public/board documents
        if user.role == 'board_member' and document.access_level in ['public', 'board']:
            return document.status == 'published'
        
        # Check explicit access permissions
        return DocumentAccess.objects.filter(
            user=user,
            document=document,
            permission='view',
            expires_at__gt=timezone.now()
        ).exists()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.get_object()
        user = self.request.user
        
        context['can_manage'] = user.role in MANAGE_DOCUMENTS
        context['can_edit'] = self.has_edit_access(user, document)
        context['can_download'] = self.has_download_access(user, document)
        context['versions'] = document.versions.all().order_by('-version_number')
        
        # Log view activity
        DocumentActivity.objects.create(
            document=document,
            user=user,
            activity_type='viewed',
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        return context
    
    def has_edit_access(self, user, document):
        """Check if user can edit document"""
        if user.role in MANAGE_DOCUMENTS:
            return True
        return DocumentAccess.objects.filter(
            user=user,
            document=document,
            permission='edit',
            expires_at__gt=timezone.now()
        ).exists()
    
    def has_download_access(self, user, document):
        """Check if user can download document"""
        if user.role in MANAGE_DOCUMENTS:
            return True
        return DocumentAccess.objects.filter(
            user=user,
            document=document,
            permission='download',
            expires_at__gt=timezone.now()
        ).exists()

class UploadDocumentView(LoginRequiredMixin, CreateView):
    """Upload view for new documents"""
    model = Document
    form_class = DocumentUploadForm
    template_name = 'documents/upload_document.html'
    success_url = reverse_lazy('documents:document_list')
    
    def dispatch(self, request, *args, **kwargs):
        """Only users who can manage documents can upload"""
        if request.user.role not in MANAGE_DOCUMENTS:
            messages.error(request, 'You do not have permission to upload documents.')
            return redirect('documents:document_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Set uploaded_by and create activity log"""
        form.instance.uploaded_by = self.request.user
        
        # Save document
        response = super().form_valid(form)
        
        # Log upload activity
        DocumentActivity.objects.create(
            document=form.instance,
            user=self.request.user,
            activity_type='uploaded',
            description=f"Uploaded '{form.instance.title}'",
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        
        messages.success(self.request, 'Document uploaded successfully!')
        return response

@role_required('it_administrator', 'company_secretary')
def manage_categories(request):
    """View to manage document categories"""
    categories = DocumentCategory.objects.all()
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.instance.created_by = request.user
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('documents:manage_categories')
    else:
        form = CategoryForm()
    
    return render(request, 'documents/manage_categories.html', {
        'categories': categories,
        'form': form,
    })

@login_required
def download_document(request, pk):
    """Download document with access check"""
    document = get_object_or_404(Document, pk=pk)
    user = request.user
    
    # Check download permissions
    if not DocumentDetailView().has_download_access(user, document):
        raise Http404("You don't have permission to download this document")
    
    # Log download activity
    DocumentActivity.objects.create(
        document=document,
        user=user,
        activity_type='downloaded',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Serve file
    if default_storage.exists(document.file.name):
        response = HttpResponse(default_storage.open(document.file.name, 'rb').read(), content_type=document.mime_type)
        response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
        response['Content-Length'] = document.file_size
        return response
    
    raise Http404("File not found")

@login_required
def document_search(request):
    """Search documents based on form criteria"""
    form = DocumentSearchForm(request.GET)
    documents = Document.objects.all()
    
    # Apply role-based filtering
    user = request.user
    if user.role == 'it_administrator':
        pass  # See all
    elif user.role == 'company_secretary':
        documents = documents.filter(status__in=['published', 'approved'])
    elif user.role == 'board_member':
        documents = documents.filter(access_level__in=['public', 'board'], status='published')
    else:
        accessible_docs = DocumentAccess.objects.filter(
            user=user, 
            permission='view',
            expires_at__gt=timezone.now()
        ).values_list('document_id', flat=True)
        documents = documents.filter(id__in=accessible_docs, status='published')
    
    if form.is_valid():
        query = form.cleaned_data.get('query', '')
        search_type = form.cleaned_data.get('search_type', 'all')
        category = form.cleaned_data.get('category')
        status = form.cleaned_data.get('status')
        access_level = form.cleaned_data.get('access_level')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        
        if query:
            if search_type == 'title':
                documents = documents.filter(title__icontains=query)
            elif search_type == 'description':
                documents = documents.filter(description__icontains=query)
            else:  # all fields
                documents = documents.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )
        
        if category:
            documents = documents.filter(category=category)
        if status:
            documents = documents.filter(status=status)
        if access_level:
            documents = documents.filter(access_level=access_level)
        if date_from:
            documents = documents.filter(created_at__date__gte=date_from)
        if date_to:
            documents = documents.filter(created_at__date__lte=date_to)
    
    return render(request, 'documents/document_list.html', {
        'documents': documents,
        'search_form': form,
        'can_manage': request.user.role in MANAGE_DOCUMENTS,
    })
