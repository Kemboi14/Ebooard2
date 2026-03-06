from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import View
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.contrib import messages
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.conf import settings
import qrcode
import io
import base64
from .forms import LoginForm, UserProfileForm, CustomPasswordChangeForm
from .models import User

# Roles that require MFA - get from settings
MFA_REQUIRED_ROLES = getattr(settings, 'MFA_REQUIRED_ROLES', [
    'board_member', 'company_secretary', 'executive_management', 
    'compliance_officer', 'it_administrator'
])

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
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
                return redirect('dashboard')
        
        return render(request, 'accounts/login.html', {'form': form})

class LogoutView(DjangoLogoutView):
    next_page = 'accounts:login'

@login_required
def ProfileView(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
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
        name=f"{user.username}'s Device",
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
                    return redirect('accounts:admin_dashboard')
                return redirect('dashboard')
        
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
