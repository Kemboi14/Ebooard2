from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect

@csrf_protect
def logout_view(request):
    """Custom logout view to handle CSRF properly"""
    logout(request)
    return redirect('accounts:login')
