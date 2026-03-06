from functools import wraps
from django.shortcuts import redirect, render
from django.conf import settings

def role_required(*roles):
    """
    Decorator to require specific user roles.
    Usage: @role_required('board_member', 'company_secretary')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            
            if request.user.role not in roles:
                return render(request, '403.html', status=403)
            
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
