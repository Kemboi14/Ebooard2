from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.templatetags.static import static
from .models import User

# Import other models for registration
try:
    from apps.evaluation.models import Evaluation, EvaluationTemplate, EvaluationCycle
    from apps.meetings.models import Meeting
    from apps.documents.models import Document
    from apps.voting.models import Resolution
    from apps.discussions.models import Post
    from apps.audit.models import SecurityLog
except ImportError:
    # Models not available, will register later
    Evaluation = EvaluationTemplate = EvaluationCycle = Meeting = None
    Document = Resolution = Post = SecurityLog = None

# Enhanced User Admin
class EnhancedUserAdmin(BaseUserAdmin):
    """Enhanced User Admin with improved UI and functionality"""
    
    list_display = (
        'get_avatar', 'email', 'get_full_name', 
        'get_role_badge', 'get_mfa_status', 'is_active', 
        'get_last_login', 'date_joined'
    )
    list_filter = (
        'role', 'is_active', 'is_staff', 'is_superuser',
        'mfa_enabled', 'department', 'date_joined', 'last_login'
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    list_per_page = 25
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Account credentials and basic information'
        }),
        (_('Personal Information'), {
            'fields': ('first_name', 'last_name', 'phone_number', 'profile_photo'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Personal details and contact information'
        }),
        (_('Professional Information'), {
            'fields': ('role', 'department', 'job_title'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Work-related information and access level'
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('wide', 'collapse', 'extrapretty'),
            'description': 'System permissions and access rights'
        }),
        (_('Security Settings'), {
            'fields': ('mfa_enabled',),
            'classes': ('wide', 'extrapretty'),
            'description': 'Two-factor authentication settings'
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse', 'extrapretty'),
            'description': 'Account activity timestamps'
        }),
    )
    
    add_fieldsets = (
        (None, {
            'fields': ('email', 'password1', 'password2'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Create new user account'
        }),
        (_('Personal Information'), {
            'fields': ('first_name', 'last_name', 'phone_number', 'profile_photo'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Personal details and contact information'
        }),
        (_('Professional Information'), {
            'fields': ('role', 'department', 'job_title'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Work-related information and access level'
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'classes': ('wide', 'extrapretty'),
            'description': 'Initial system permissions'
        }),
    )
    
    # Custom display methods
    def get_avatar(self, obj):
        if obj.profile_photo:
            return format_html(
                '<img src="{}" width="32" height="32" style="border-radius: 50%; object-fit: cover;" />',
                obj.profile_photo.url
            )
        return format_html(
            '<div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #667eea, #764ba2); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">{}</div>',
            obj.email[0].upper() if obj.email else 'U'
        )
    get_avatar.short_description = 'Avatar'
    get_avatar.admin_order_field = 'email'
    
    def get_full_name(self, obj):
        return obj.get_full_name() or f"{obj.first_name} {obj.last_name}".strip() or obj.email
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'first_name'
    
    def get_role_badge(self, obj):
        colors = {
            'it_administrator': '#dc3545',
            'company_secretary': '#28a745', 
            'executive_management': '#ffc107',
            'compliance_officer': '#17a2b8',
            'board_member': '#6f42c1',
            'shareholder': '#6c757d'
        }
        color = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase;">{}</span>',
            color, obj.role.replace('_', ' ').title()
        )
    get_role_badge.short_description = 'Role'
    get_role_badge.admin_order_field = 'role'
    
    def get_mfa_status(self, obj):
        if obj.mfa_enabled:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Enabled</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ Disabled</span>'
        )
    get_mfa_status.short_description = 'MFA'
    get_mfa_status.admin_order_field = 'mfa_enabled'
    
    def get_last_login(self, obj):
        if obj.last_login:
            return obj.last_login.strftime('%b %d, %Y %H:%M')
        return 'Never'
    get_last_login.short_description = 'Last Login'
    get_last_login.admin_order_field = 'last_login'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Non-superusers can only manage regular users
        return qs.filter(is_superuser=False)
    
    def get_readonly_fields(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return ['is_superuser', 'user_permissions']
        return []
    
    # Custom actions
    actions = ['enable_mfa', 'disable_mfa']
    
    def enable_mfa(self, request, queryset):
        updated = queryset.update(mfa_enabled=True)
        self.message_user(request, f'{updated} users had MFA enabled.', level='success')
    enable_mfa.short_description = 'Enable MFA for selected users'
    
    def disable_mfa(self, request, queryset):
        updated = queryset.update(mfa_enabled=False)
        self.message_user(request, f'{updated} users had MFA disabled.', level='warning')
    disable_mfa.short_description = 'Disable MFA for selected users'

# Enhanced Admin Site Configuration
class EnhancedAdminSite(admin.AdminSite):
    """Custom admin site with improved branding and UI"""
    
    site_header = 'Enwealth Board Portal'
    site_title = 'Enwealth Administration'
    index_title = 'Dashboard'
    
    def each_context(self, request):
        context = super().each_context(request)
        context.update({
            'site_header': 'Enwealth Board Portal',
            'site_title': 'Enwealth Administration',
            'index_title': 'Admin Dashboard',
            'has_permission': True,
        })
        return context

# Create custom admin site instance
enhanced_admin = EnhancedAdminSite(name='enhanced_admin')

# Register User model with enhanced admin site
enhanced_admin.register(User, EnhancedUserAdmin)

# Register other models if available
if Evaluation:
    @enhanced_admin.register(Evaluation)
    class EvaluationAdmin(admin.ModelAdmin):
        list_display = ('title', 'evaluator', 'evaluatee', 'status', 'percentage_score', 'created_at')
        list_filter = ('status', 'template', 'created_at', 'percentage_score')
        search_fields = ('title', 'evaluator__email', 'evaluatee__email')
        ordering = ('-created_at',)
        list_per_page = 20

if EvaluationTemplate:
    @enhanced_admin.register(EvaluationTemplate)
    class EvaluationTemplateAdmin(admin.ModelAdmin):
        list_display = ('name', 'category', 'is_active', 'created_by', 'created_at')
        list_filter = ('category', 'is_active', 'created_at')
        search_fields = ('name', 'description')
        ordering = ('-created_at',)
        list_per_page = 20

if EvaluationCycle:
    @enhanced_admin.register(EvaluationCycle)
    class EvaluationCycleAdmin(admin.ModelAdmin):
        list_display = ('name', 'start_date', 'end_date', 'is_active', 'created_at')
        list_filter = ('is_active', 'start_date', 'end_date')
        search_fields = ('name', 'description')
        ordering = ('-created_at',)
        list_per_page = 20

if Meeting:
    @enhanced_admin.register(Meeting)
    class MeetingAdmin(admin.ModelAdmin):
        list_display = ('title', 'start_time', 'meeting_type', 'status', 'location')
        list_filter = ('meeting_type', 'status', 'start_time')
        search_fields = ('title', 'description', 'location')
        ordering = ('-start_time',)
        list_per_page = 20

if Document:
    @enhanced_admin.register(Document)
    class DocumentAdmin(admin.ModelAdmin):
        list_display = ('title', 'document_type', 'version', 'uploaded_by', 'uploaded_at')
        list_filter = ('document_type', 'uploaded_at', 'version')
        search_fields = ('title', 'description')
        ordering = ('-uploaded_at',)
        list_per_page = 20

if Resolution:
    @enhanced_admin.register(Resolution)
    class ResolutionAdmin(admin.ModelAdmin):
        list_display = ('title', 'status', 'voting_deadline', 'created_by', 'created_at')
        list_filter = ('status', 'created_at', 'voting_deadline')
        search_fields = ('title', 'description')
        ordering = ('-created_at',)
        list_per_page = 20

if Post:
    @enhanced_admin.register(Post)
    class PostAdmin(admin.ModelAdmin):
        list_display = ('title', 'author', 'category', 'is_pinned', 'created_at')
        list_filter = ('category', 'is_pinned', 'created_at')
        search_fields = ('title', 'content')
        ordering = ('-created_at',)
        list_per_page = 20

if SecurityLog:
    @enhanced_admin.register(SecurityLog)
    class SecurityLogAdmin(admin.ModelAdmin):
        list_display = ('action', 'level', 'user', 'ip_address', 'created_at')
        list_filter = ('level', 'action', 'created_at')
        search_fields = ('action', 'user__email', 'ip_address')
        ordering = ('-created_at',)
        list_per_page = 50
        readonly_fields = ('action', 'level', 'user', 'ip_address', 'user_agent', 'created_at')
