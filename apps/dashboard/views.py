from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import User

@login_required
def DashboardView(request):
    """
    Role-based dashboard view that shows different content based on user role
    """
    user = request.user
    context = {
        'current_date': timezone.now().date(),
        'user': user,
    }
    
    # Common data for all roles
    context.update({
        'unread_notifications_count': 0,  # Will be implemented with notifications app
        'recent_notifications': [],  # Will be implemented with notifications app
    })
    
    # Role-specific dashboard content
    if user.role == 'board_member':
        context.update(_get_board_member_context(user))
    elif user.role == 'company_secretary':
        context.update(_get_company_secretary_context(user))
    elif user.role == 'compliance_officer':
        context.update(_get_compliance_officer_context(user))
    elif user.role == 'it_administrator':
        context.update(_get_it_administrator_context(user))
    elif user.role == 'executive_management':
        context.update(_get_executive_management_context(user))
    elif user.role == 'internal_audit':
        context.update(_get_internal_audit_context(user))
    
    return render(request, 'dashboard/dashboard.html', context)

def _get_board_member_context(user):
    """Dashboard context for Board Members"""
    return {
        'upcoming_meetings': [],  # Will be populated from meetings app
        'pending_votes': [],      # Will be populated from voting app
        'pending_policies': [],   # Will be populated from policy app
        'recent_documents': [],   # Will be populated from documents app
        'dashboard_stats': {
            'meetings_this_month': 0,
            'pending_actions': 0,
            'documents_to_review': 0,
        }
    }

def _get_company_secretary_context(user):
    """Dashboard context for Company Secretary"""
    return {
        'all_upcoming_meetings': [],  # Will be populated from meetings app
        'draft_resolutions': [],      # Will be populated from voting app
        'meetings_without_minutes': [],  # Will be populated from meetings app
        'recent_audit_events': [],    # Will be populated from audit app
        'dashboard_stats': {
            'total_meetings': 0,
            'draft_resolutions': 0,
            'pending_minutes': 0,
        }
    }

def _get_compliance_officer_context(user):
    """Dashboard context for Compliance Officer"""
    return {
        'risk_counts': {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
        },
        'overdue_policies': [],       # Will be populated from policy app
        'audit_summary': [],         # Will be populated from audit app
        'dashboard_stats': {
            'total_risks': 0,
            'overdue_policies': 0,
            'compliance_score': 0,
        }
    }

def _get_it_administrator_context(user):
    """Dashboard context for IT Administrator"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    return {
        'total_users': User.objects.filter(is_active=True).count(),
        'active_users_30d': User.objects.filter(
            last_login__gte=thirty_days_ago
        ).count(),
        'failed_logins_today': 0,   # Will be populated from audit app
        'recent_activity': [],       # Will be populated from audit app
        'storage_used': 0,           # Will be populated from documents app
        'dashboard_stats': {
            'total_users': User.objects.filter(is_active=True).count(),
            'active_users': User.objects.filter(
                last_login__gte=thirty_days_ago
            ).count(),
            'system_health': 100,     # Placeholder
        }
    }

def _get_executive_management_context(user):
    """Dashboard context for Executive Management"""
    current_month = timezone.now().replace(day=1)
    
    return {
        'recent_decisions': [],      # Will be populated from voting app
        'meetings_this_month': 0,   # Will be populated from meetings app
        'dashboard_stats': {
            'decisions_this_month': 0,
            'meetings_this_month': 0,
            'board_engagement': 0,
        }
    }

def _get_internal_audit_context(user):
    """Dashboard context for Internal Audit"""
    today = timezone.now().date()
    
    return {
        'audit_today': 0,           # Will be populated from audit app
        'user_action_summary': [],  # Will be populated from audit app
        'dashboard_stats': {
            'audits_today': 0,
            'high_risk_activities': 0,
            'compliance_issues': 0,
        }
    }
