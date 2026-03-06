from django.shortcuts import render

def csrf_failure(request, reason=""):
    """Custom CSRF failure view"""
    return render(request, 'accounts/csrf_failure.html', {
        'reason': reason,
        'title': 'CSRF Verification Failed'
    })
