from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Logout view that accepts both GET and POST requests.
    CSRF is exempt because logout is a safe operation — the worst a CSRF
    attack can do is log the user out, which is not a security risk.
    """
    logout(request)
    return redirect("accounts:login")
