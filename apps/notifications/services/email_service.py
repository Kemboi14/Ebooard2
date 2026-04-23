"""
Email notification service for the governance portal.
Handles sending emails for user creation, motion notifications, and other system events.
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_user_welcome_email(user_id):
    """
    Send welcome email to newly created user.
    """
    from apps.accounts.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'portal_name': 'Enwealth Governance Portal',
            'current_year': timezone.now().year,
        }
        
        subject = f"Welcome to {context['portal_name']}"
        
        html_message = render_to_string('emails/user_welcome.html', context)
        plain_message = render_to_string('emails/user_welcome.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return False


@shared_task
def send_motion_notification_email(motion_id):
    """
    Send notification email when a motion is proposed.
    """
    from apps.voting.models import Motion, CommitteeMembership
    
    try:
        motion = Motion.objects.get(id=motion_id)
        
        # Get all committee members eligible to vote
        # This will be updated once committee membership is implemented
        eligible_voters = motion.eligible_voters.all()
        
        context = {
            'motion': motion,
            'portal_name': 'Enwealth Governance Portal',
            'current_year': timezone.now().year,
        }
        
        subject = f"New Motion Proposed: {motion.title}"
        
        html_message = render_to_string('emails/motion_proposed.html', context)
        plain_message = render_to_string('emails/motion_proposed.txt', context)
        
        recipient_emails = [voter.email for voter in eligible_voters if voter.email]
        
        if recipient_emails:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Motion notification sent to {len(recipient_emails)} recipients")
            return True
        else:
            logger.warning(f"No eligible voters found for motion {motion_id}")
            return False
            
    except Motion.DoesNotExist:
        logger.error(f"Motion with id {motion_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending motion notification: {str(e)}")
        return False


@shared_task
def send_policy_expiry_notification(policy_id, days_until_expiry):
    """
    Send notification when a policy is about to expire.
    """
    from apps.policy.models import Policy
    
    try:
        policy = Policy.objects.get(id=policy_id)
        
        context = {
            'policy': policy,
            'days_until_expiry': days_until_expiry,
            'portal_name': 'Enwealth Governance Portal',
            'current_year': timezone.now().year,
        }
        
        subject = f"Policy Expiring Soon: {policy.title}"
        
        html_message = render_to_string('emails/policy_expiry_warning.html', context)
        plain_message = render_to_string('emails/policy_expiry_warning.txt', context)
        
        # Send to compliance officers and IT administrators
        from apps.accounts.models import User
        recipient_emails = User.objects.filter(
            role__in=['compliance_officer', 'it_administrator'],
            is_active=True
        ).values_list('email', flat=True)
        
        if recipient_emails:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(recipient_emails),
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Policy expiry notification sent for policy {policy_id}")
            return True
        else:
            logger.warning(f"No recipients found for policy expiry notification")
            return False
            
    except Policy.DoesNotExist:
        logger.error(f"Policy with id {policy_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending policy expiry notification: {str(e)}")
        return False


@shared_task
def send_account_termination_notification(user_id, terminated_by_id, reason):
    """
    Send notification when an account is terminated.
    """
    from apps.accounts.models import User
    
    try:
        user = User.objects.get(id=user_id)
        terminated_by = User.objects.get(id=terminated_by_id)
        
        context = {
            'user': user,
            'terminated_by': terminated_by,
            'reason': reason,
            'portal_name': 'Enwealth Governance Portal',
            'current_year': timezone.now().year,
        }
        
        subject = f"Account Terminated: {user.get_full_name()}"
        
        html_message = render_to_string('emails/account_terminated.html', context)
        plain_message = render_to_string('emails/account_terminated.txt', context)
        
        # Send to IT administrators
        recipient_emails = User.objects.filter(
            role='it_administrator',
            is_active=True
        ).values_list('email', flat=True)
        
        if recipient_emails:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(recipient_emails),
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Account termination notification sent for user {user_id}")
            return True
        else:
            logger.warning(f"No IT administrators found for termination notification")
            return False
            
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending account termination notification: {str(e)}")
        return False
