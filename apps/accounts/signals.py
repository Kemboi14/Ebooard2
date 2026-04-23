"""
Signal handlers for the accounts app.
Triggers email notifications and other actions on user lifecycle events.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import User, UserSession
from apps.notifications.services.email_service import send_user_welcome_email
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def send_welcome_email_on_creation(sender, instance, created, **kwargs):
    """
    Send welcome email when a new user is created.
    """
    if created:
        try:
            send_user_welcome_email.delay(str(instance.id))
            logger.info(f"Welcome email queued for user {instance.email}")
        except Exception as e:
            logger.error(f"Failed to queue welcome email for user {instance.email}: {str(e)}")


@receiver(user_logged_in)
def create_user_session(sender, request, user, **kwargs):
    """
    Create or update UserSession when user logs in.
    """
    from django.utils import timezone
    
    # Get or create session
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    
    # Terminate any existing active sessions for this user
    UserSession.objects.filter(
        user=user,
        status='active'
    ).update(
        status='logout',
        logout_at=timezone.now()
    )
    
    # Create new session
    UserSession.objects.create(
        user=user,
        session_key=session_key,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        status='active',
        login_at=timezone.now(),
        last_activity=timezone.now()
    )
    
    logger.info(f"Session created for user {user.email}")


@receiver(user_logged_out)
def terminate_user_session(sender, request, user, **kwargs):
    """
    Terminate UserSession when user logs out.
    """
    from django.utils import timezone
    
    session_key = request.session.session_key
    if session_key and user:
        UserSession.objects.filter(
            user=user,
            session_key=session_key,
            status='active'
        ).update(
            status='logout',
            logout_at=timezone.now()
        )
        
        logger.info(f"Session terminated for user {user.email}")


def get_client_ip(request):
    """
    Get client IP address from request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
