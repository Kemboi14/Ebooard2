"""
Signal handlers for the voting app.
Triggers email notifications when motions are proposed or status changes.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Motion
from apps.notifications.services.email_service import send_motion_notification_email
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Motion)
def notify_on_motion_proposed(sender, instance, created, **kwargs):
    """
    Send notification when a motion is proposed.
    """
    if not created:
        # Check if status changed to 'proposed'
        try:
            old_instance = Motion.objects.get(id=instance.id)
            if old_instance.status != 'proposed' and instance.status == 'proposed':
                try:
                    send_motion_notification_email.delay(str(instance.id))
                    logger.info(f"Motion notification queued for motion {instance.id}")
                except Exception as e:
                    logger.error(f"Failed to queue motion notification for motion {instance.id}: {str(e)}")
        except Motion.DoesNotExist:
            pass
