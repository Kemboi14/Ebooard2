from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render

class RoleRequiredMixin(LoginRequiredMixin):
    """
    Mixin to require specific user roles for class-based views.
    Usage: class MyView(RoleRequiredMixin): allowed_roles = ['board_member']
    """
    allowed_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.role not in self.allowed_roles:
            return render(request, '403.html', status=403)
        
        return super().dispatch(request, *args, **kwargs)
