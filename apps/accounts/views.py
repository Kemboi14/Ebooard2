from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import View, ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib import messages
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.conf import settings
import qrcode
import io
import base64
from .forms import LoginForm, UserProfileForm, CustomPasswordChangeForm
from .models import (
    User, SSOProvider, UserSSOIdentity, UserSession, EncryptionKey,
    Language, Translation, Committee, CommitteeMembership, Bookmark, FieldEditPermission
)

# Roles that require MFA - get from settings
MFA_REQUIRED_ROLES = getattr(settings, 'MFA_REQUIRED_ROLES', [
    'board_member', 'company_secretary', 'executive_management', 
    'compliance_officer', 'it_administrator'
])

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        form = LoginForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            # Track failed attempts
            key = f'login_attempts_{email}'
            attempts = cache.get(key, 0)

            if attempts >= 5:
                ttl = cache.ttl(key)
                form.add_error(None, f"Account locked. Try again in {ttl // 60} minutes.")
                return render(request, 'accounts/login.html', {'form': form})

            user = authenticate(request, username=email, password=password)

            if user is None:
                cache.set(key, attempts + 1, timeout=1800)  # 30 minutes
                remaining = 5 - attempts - 1
                form.add_error(None, f"Invalid credentials. {remaining} attempts remaining.")
                return render(request, 'accounts/login.html', {'form': form})

            # Check MFA requirement
            if user.role in MFA_REQUIRED_ROLES:
                if not user.mfa_enabled:
                    # Force MFA setup
                    cache.delete(key)  # Reset attempts on success
                    login(request, user)
                    return redirect('accounts:enable_2fa')
                else:
                    # Store user ID for MFA verification
                    request.session['pre_mfa_user_id'] = str(user.pk)
                    return redirect('accounts:login_2fa')
            else:
                # No MFA required, login directly
                cache.delete(key)  # Reset attempts on success
                login(request, user)
                return redirect('/dashboard/')

        return render(request, 'accounts/login.html', {'form': form})

class LogoutView(DjangoLogoutView):
    next_page = 'accounts:login'

@login_required
def ProfileView(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            try:
                # Check if profile_photo is in the files
                if 'profile_photo' in request.FILES:
                    messages.info(request, f'File received: {request.FILES["profile_photo"].name}')
                else:
                    messages.info(request, 'No file received in request.FILES')
                
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('accounts:profile')
            except Exception as e:
                messages.error(request, f'Error saving profile: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})

@login_required
@csrf_protect
def enable_2fa(request):
    """Enable two-factor authentication"""
    user = request.user
    
    # Check if user already has 2FA enabled
    if devices_for_user(user):
        messages.info(request, "Two-factor authentication is already enabled.")
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        token = request.POST.get('otp_token')
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        
        if device and device.verify_token(token):
            device.confirmed = True
            device.save()
            messages.success(request, "Two-factor authentication enabled successfully!")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Invalid authentication code. Please try again.")
    
    # Create new TOTP device
    device = TOTPDevice.objects.create(
        user=user,
        name=f"{user.get_full_name() or user.email}'s Device",
        confirmed=False
    )
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(device.config_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code_data = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'qr_code_url': f"data:image/png;base64,{qr_code_data}",
        'secret_key': device.key,
    }
    
    return render(request, 'accounts/enable_2fa.html', context)

@login_required
@csrf_protect
def login_2fa(request):
    """Handle two-factor authentication login"""
    if request.method == 'POST':
        token = request.POST.get('otp_token')
        user = request.user  # User should be in session from first login step

        # Verify OTP token
        for device in devices_for_user(user):
            if device.verify_token(token):
                login(request, user)
                messages.success(request, "Login successful!")

                # Clear login attempts
                cache.delete(f'login_attempts_{user.email}')

                # Redirect based on user role
                if user.role == 'it_administrator':
                    return redirect('/auth/admin-dashboard/')
                return redirect('/dashboard/')

        messages.error(request, "Invalid authentication code.")

    return render(request, 'accounts/login_2fa.html', {'form': None})

@login_required
def admin_dashboard(request):
    """Enhanced admin dashboard"""
    if request.user.role != 'it_administrator':
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('dashboard')
    
    # Get dashboard statistics
    from apps.evaluation.models import Evaluation
    from apps.meetings.models import Meeting
    from apps.audit.models import SecurityLog
    
    total_users = User.objects.count()
    active_evaluations = Evaluation.objects.filter(status__in=['in_progress', 'submitted']).count()
    pending_reviews = Evaluation.objects.filter(status='submitted').count()
    total_meetings = Meeting.objects.count()
    upcoming_meetings = Meeting.objects.filter(
        start_time__gte=timezone.now(),
        start_time__lte=timezone.now() + timezone.timedelta(days=7)
    ).count()
    security_alerts = SecurityLog.objects.filter(
        level='HIGH',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).count()
    critical_alerts = SecurityLog.objects.filter(
        level='CRITICAL',
        created_at__gte=timezone.now() - timezone.timedelta(days=1)
    ).count()
    
    # User growth (simplified calculation)
    user_growth = 5  # This would be calculated from historical data
    
    # Recent activities (mock data for now)
    recent_activities = [
        {
            'type': 'evaluation',
            'description': 'New evaluation created for John Doe',
            'timestamp': timezone.now() - timezone.timedelta(hours=2)
        },
        {
            'type': 'meeting',
            'description': 'Board meeting scheduled for tomorrow',
            'timestamp': timezone.now() - timezone.timedelta(hours=4)
        },
        {
            'type': 'security',
            'description': 'Failed login attempt detected',
            'timestamp': timezone.now() - timezone.timedelta(hours=6)
        }
    ]
    
    context = {
        'total_users': total_users,
        'active_evaluations': active_evaluations,
        'pending_reviews': pending_reviews,
        'total_meetings': total_meetings,
        'upcoming_meetings': upcoming_meetings,
        'security_alerts': security_alerts,
        'critical_alerts': critical_alerts,
        'user_growth': user_growth,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)

@login_required
def ChangePasswordView(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:change_password')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


# ─── SSO Provider Views ─────────────────────────────────────────────────────────

class SSOProviderListView(LoginRequiredMixin, ListView):
    """List all SSO providers"""
    model = SSOProvider
    template_name = 'accounts/sso_providers.html'
    context_object_name = 'providers'
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role not in ['it_administrator', 'company_secretary']:
            queryset = queryset.filter(status='active')
        return queryset


class SSOProviderDetailView(LoginRequiredMixin, DetailView):
    """View SSO provider details"""
    model = SSOProvider
    template_name = 'accounts/sso_provider_detail.html'
    context_object_name = 'provider'


class SSOProviderCreateView(LoginRequiredMixin, CreateView):
    """Create a new SSO provider"""
    model = SSOProvider
    template_name = 'accounts/sso_provider_form.html'
    fields = ['name', 'provider_type', 'entity_id', 'sso_url', 'slo_url', 'certificate', 'role_mapping', 'auto_provisioning', 'security_settings', 'metadata']
    success_url = reverse_lazy('accounts:sso_providers')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'SSO provider created successfully.')
        return super().form_valid(form)


# ─── Session Management Views ───────────────────────────────────────────────────

class UserSessionListView(LoginRequiredMixin, ListView):
    """List user sessions"""
    model = UserSession
    template_name = 'accounts/user_sessions.html'
    context_object_name = 'sessions'
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.GET.get('user')
        if user_id and self.request.user.role in ['it_administrator', 'company_secretary']:
            queryset = queryset.filter(user_id=user_id)
        else:
            queryset = queryset.filter(user=self.request.user)
        return queryset


@login_required
@require_POST
def revoke_session(request, pk):
    """Revoke a user session"""
    session = get_object_or_404(UserSession, pk=pk)
    
    if session.user != request.user and request.user.role not in ['it_administrator', 'company_secretary']:
        messages.error(request, "You don't have permission to revoke this session.")
        return redirect('accounts:user_sessions')
    
    session.status = 'revoked'
    session.save()
    messages.success(request, 'Session revoked successfully.')
    return redirect('accounts:user_sessions')


@login_required
@require_POST
def revoke_all_other_sessions(request):
    """Revoke all other sessions for the current user"""
    UserSession.objects.filter(
        user=request.user,
        status='active'
    ).exclude(session_key=request.session.session_key).update(status='revoked')
    
    messages.success(request, 'All other sessions revoked successfully.')
    return redirect('accounts:user_sessions')


# ─── Encryption Key Management Views ───────────────────────────────────────────

class EncryptionKeyListView(LoginRequiredMixin, ListView):
    """List all encryption keys"""
    model = EncryptionKey
    template_name = 'accounts/encryption_keys.html'
    context_object_name = 'keys'
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role not in ['it_administrator']:
            queryset = queryset.filter(status='active')
        return queryset


class EncryptionKeyCreateView(LoginRequiredMixin, CreateView):
    """Create a new encryption key"""
    model = EncryptionKey
    template_name = 'accounts/encryption_key_form.html'
    fields = ['name', 'key_type', 'rotation_interval_days']
    success_url = reverse_lazy('accounts:encryption_keys')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Encryption key created successfully.')
        return super().form_valid(form)


@login_required
@require_POST
def rotate_encryption_key(request, pk):
    """Rotate an encryption key"""
    key = get_object_or_404(EncryptionKey, pk=pk)
    
    if request.user.role not in ['it_administrator']:
        messages.error(request, "You don't have permission to rotate encryption keys.")
        return redirect('accounts:encryption_keys')
    
    key.status = 'rotating'
    key.save()
    
    # In production, this would trigger actual key rotation
    key.status = 'active'
    key.last_rotated_at = timezone.now()
    key.next_rotation_at = timezone.now() + timezone.timedelta(days=key.rotation_interval_days)
    key.save()
    
    messages.success(request, 'Encryption key rotated successfully.')
    return redirect('accounts:encryption_keys')


# ─── Multi-Language Support Views ───────────────────────────────────────────────

class LanguageListView(LoginRequiredMixin, ListView):
    """List all supported languages"""
    model = Language
    template_name = 'accounts/languages.html'
    context_object_name = 'languages'
    ordering = ['name']


class TranslationListView(LoginRequiredMixin, ListView):
    """List all translations"""
    model = Translation
    template_name = 'accounts/translations.html'
    context_object_name = 'translations'
    ordering = ['key']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        module = self.request.GET.get('module')
        if module:
            queryset = queryset.filter(module=module)
        return queryset


class TranslationCreateView(LoginRequiredMixin, CreateView):
    """Create a new translation"""
    model = Translation
    template_name = 'accounts/translation_form.html'
    fields = ['key', 'context', 'module', 'translations']
    success_url = reverse_lazy('accounts:translations')
    
    def form_valid(self, form):
        messages.success(self.request, 'Translation created successfully.')
        return super().form_valid(form)


class TranslationUpdateView(LoginRequiredMixin, UpdateView):
    """Update a translation"""
    model = Translation
    template_name = 'accounts/translation_form.html'
    fields = ['key', 'context', 'module', 'translations']
    success_url = reverse_lazy('accounts:translations')
    
    def form_valid(self, form):
        messages.success(self.request, 'Translation updated successfully.')
        return super().form_valid(form)


# ============================================================================
# Committee Views
# ============================================================================

class CommitteeListView(LoginRequiredMixin, ListView):
    """List all committees"""
    model = Committee
    template_name = 'accounts/committee_list.html'
    context_object_name = 'committees'
    ordering = ['name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(is_active=True)
        return queryset


class CommitteeDetailView(LoginRequiredMixin, DetailView):
    """View committee details"""
    model = Committee
    template_name = 'accounts/committee_detail.html'
    context_object_name = 'committee'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['memberships'] = self.object.memberships.select_related('user').all()
        return context


class CommitteeCreateView(LoginRequiredMixin, CreateView):
    """Create a new committee"""
    model = Committee
    template_name = 'accounts/committee_form.html'
    fields = ['name', 'description', 'meeting_type', 'is_active', 'meeting_frequency']
    success_url = reverse_lazy('accounts:committees')
    
    def form_valid(self, form):
        messages.success(self.request, 'Committee created successfully.')
        return super().form_valid(form)


class CommitteeUpdateView(LoginRequiredMixin, UpdateView):
    """Update a committee"""
    model = Committee
    template_name = 'accounts/committee_form.html'
    fields = ['name', 'description', 'meeting_type', 'is_active', 'meeting_frequency']
    success_url = reverse_lazy('accounts:committees')
    
    def form_valid(self, form):
        messages.success(self.request, 'Committee updated successfully.')
        return super().form_valid(form)


# ============================================================================
# CommitteeMembership Views
# ============================================================================

class CommitteeMembershipListView(LoginRequiredMixin, ListView):
    """List all committee memberships"""
    model = CommitteeMembership
    template_name = 'accounts/committee_membership_list.html'
    context_object_name = 'memberships'
    ordering = ['committee', '-joined_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        committee_id = self.request.GET.get('committee')
        if committee_id:
            queryset = queryset.filter(committee_id=committee_id)
        return queryset


class CommitteeMembershipCreateView(LoginRequiredMixin, CreateView):
    """Add a member to a committee"""
    model = CommitteeMembership
    template_name = 'accounts/committee_membership_form.html'
    fields = ['committee', 'user', 'role', 'has_voting_rights']
    success_url = reverse_lazy('accounts:committee_memberships')
    
    def form_valid(self, form):
        messages.success(self.request, 'Committee membership added successfully.')
        return super().form_valid(form)


class CommitteeMembershipUpdateView(LoginRequiredMixin, UpdateView):
    """Update committee membership"""
    model = CommitteeMembership
    template_name = 'accounts/committee_membership_form.html'
    fields = ['role', 'has_voting_rights', 'left_at']
    success_url = reverse_lazy('accounts:committee_memberships')
    
    def form_valid(self, form):
        messages.success(self.request, 'Committee membership updated successfully.')
        return super().form_valid(form)


# ============================================================================
# Bookmark Views
# ============================================================================

class BookmarkListView(LoginRequiredMixin, ListView):
    """List user's bookmarks"""
    model = Bookmark
    template_name = 'accounts/bookmark_list.html'
    context_object_name = 'bookmarks'
    ordering = ['-is_pinned', '-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(user=self.request.user)
        folder = self.request.GET.get('folder')
        if folder:
            queryset = queryset.filter(folder=folder)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['folders'] = Bookmark.objects.filter(
            user=self.request.user
        ).values_list('folder', flat=True).distinct()
        return context


class BookmarkCreateView(LoginRequiredMixin, CreateView):
    """Create a new bookmark"""
    model = Bookmark
    template_name = 'accounts/bookmark_form.html'
    fields = ['bookmark_type', 'target_id', 'target_url', 'title', 'description', 'folder', 'is_pinned']
    success_url = reverse_lazy('accounts:bookmarks')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Bookmark created successfully.')
        return super().form_valid(form)


class BookmarkUpdateView(LoginRequiredMixin, UpdateView):
    """Update a bookmark"""
    model = Bookmark
    template_name = 'accounts/bookmark_form.html'
    fields = ['title', 'description', 'folder', 'is_pinned']
    success_url = reverse_lazy('accounts:bookmarks')
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Bookmark updated successfully.')
        return super().form_valid(form)


class BookmarkDeleteView(LoginRequiredMixin, View):
    """Delete a bookmark"""
    def post(self, request, pk):
        bookmark = get_object_or_404(Bookmark, pk=pk, user=request.user)
        bookmark.delete()
        messages.success(request, 'Bookmark deleted successfully.')
        return redirect('accounts:bookmarks')


# ============================================================================
# FieldEditPermission Views
# ============================================================================

class FieldEditPermissionListView(LoginRequiredMixin, ListView):
    """List all field edit permissions"""
    model = FieldEditPermission
    template_name = 'accounts/field_permission_list.html'
    context_object_name = 'permissions'
    ordering = ['model_name', 'field_name']


class FieldEditPermissionCreateView(LoginRequiredMixin, CreateView):
    """Create a new field edit permission"""
    model = FieldEditPermission
    template_name = 'accounts/field_permission_form.html'
    fields = ['model_name', 'field_name', 'allowed_roles', 'freeze_condition', 
              'freeze_on_status', 'freeze_after_date', 'freeze_after_days', 
              'require_approval', 'description', 'is_active']
    success_url = reverse_lazy('accounts:field_permissions')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Field edit permission created successfully.')
        return super().form_valid(form)


class FieldEditPermissionUpdateView(LoginRequiredMixin, UpdateView):
    """Update a field edit permission"""
    model = FieldEditPermission
    template_name = 'accounts/field_permission_form.html'
    fields = ['allowed_roles', 'freeze_condition', 'freeze_on_status', 
              'freeze_after_date', 'freeze_after_days', 'require_approval', 
              'description', 'is_active']
    success_url = reverse_lazy('accounts:field_permissions')
    
    def form_valid(self, form):
        messages.success(self.request, 'Field edit permission updated successfully.')
        return super().form_valid(form)
