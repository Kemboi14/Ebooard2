from .permissions import *

def user_permissions(request):
    if not request.user.is_authenticated:
        return {}
    
    role = request.user.role
    return {
        'user_role': role,
        'can_manage_meetings': role in MANAGE_MEETINGS,
        'can_vote': role in CAN_VOTE,
        'can_view_audit': role in VIEW_AUDIT,
        'can_manage_risk': role in MANAGE_RISK,
        'can_manage_policies': role in MANAGE_POLICIES,
        'is_admin': role in ADMIN_ROLES,
        'mfa_required': role in MFA_REQUIRED_ROLES,
    }
