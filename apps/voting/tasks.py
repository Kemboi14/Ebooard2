import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_close_expired_resolutions(self):
    """
    Automatically close voting on motions whose deadline has passed
    but are still in 'voting' status.

    Runs every 5 minutes (configured in settings.CELERY_BEAT_SCHEDULE).
    """
    from .models import Motion

    try:
        expired = Motion.objects.filter(
            status="voting",
            voting_deadline__lt=timezone.now(),
            voting_ended_at__isnull=True,
        )

        closed = 0
        failed_ids = []

        for motion in expired:
            try:
                result = motion.close_voting()
                logger.info(
                    "Auto-closed motion %s (%s) — result: %s",
                    motion.pk,
                    motion.title,
                    result,
                )
                closed += 1
            except Exception as exc:
                logger.error(
                    "Failed to auto-close motion %s: %s",
                    motion.pk,
                    exc,
                    exc_info=True,
                )
                failed_ids.append(str(motion.pk))

        summary = f"auto_close_expired_resolutions: closed {closed} motion(s)."
        if failed_ids:
            summary += f" Failed for: {', '.join(failed_ids)}"

        logger.info(summary)
        return summary

    except Exception as exc:
        logger.error(
            "auto_close_expired_resolutions task error: %s", exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def notify_voting_deadline_approaching(self):
    """
    Send notifications to eligible voters when a motion's voting
    deadline is within the next 24 hours and they haven't voted yet.
    """
    from .models import Motion, Vote

    try:
        from django.utils.timezone import timedelta

        window_end = timezone.now() + timedelta(hours=24)
        window_start = timezone.now()

        upcoming_deadline_motions = Motion.objects.filter(
            status="voting",
            voting_deadline__gte=window_start,
            voting_deadline__lte=window_end,
            voting_ended_at__isnull=True,
        ).prefetch_related("votes")

        notified = 0

        for motion in upcoming_deadline_motions:
            voters_who_voted = motion.votes.values_list("voter_id", flat=True)

            # Get eligible voters from the linked voting session (if any)
            sessions = motion.sessions.filter(status="active")
            eligible_voters = []
            for session in sessions:
                for voter in session.eligible_voters.exclude(pk__in=voters_who_voted):
                    eligible_voters.append(voter)

            for voter in eligible_voters:
                try:
                    _send_deadline_reminder(voter, motion)
                    notified += 1
                except Exception as exc:
                    logger.warning(
                        "Could not send deadline reminder to %s for motion %s: %s",
                        voter.email,
                        motion.pk,
                        exc,
                    )

        summary = f"notify_voting_deadline_approaching: sent {notified} reminder(s)."
        logger.info(summary)
        return summary

    except Exception as exc:
        logger.error(
            "notify_voting_deadline_approaching task error: %s", exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=120)


def _send_deadline_reminder(user, motion):
    """
    Internal helper — sends an in-app notification (and optionally email)
    reminding a voter that a deadline is approaching.
    """
    try:
        from apps.notifications.models import Notification  # type: ignore

        hours_left = max(
            0,
            int((motion.voting_deadline - timezone.now()).total_seconds() / 3600),
        )

        Notification.objects.create(
            recipient=user,
            title="Voting Deadline Approaching",
            message=(
                f'The voting deadline for "{motion.title}" is in approximately '
                f"{hours_left} hour(s). Please cast your vote before it closes."
            ),
            notification_type="voting",
            related_object_id=str(motion.pk),
        )
    except Exception as exc:
        # Notification module might not have the expected API — log and continue
        logger.debug("Could not create in-app notification for %s: %s", user.email, exc)


@shared_task
def recalculate_vote_results(motion_pk):
    """
    Recalculate and update the VoteResult snapshot for a given motion.
    Useful if votes are manually adjusted by an administrator.
    """
    from .models import Motion, VoteResult

    try:
        motion = Motion.objects.get(pk=motion_pk)

        if motion.status not in ("passed", "failed"):
            logger.warning(
                "recalculate_vote_results called on motion %s with status '%s' — skipping.",
                motion_pk,
                motion.status,
            )
            return f"Skipped: motion status is '{motion.status}'"

        result, created = VoteResult.objects.update_or_create(
            motion=motion,
            defaults=dict(
                total_votes=motion.total_votes,
                yes_votes=motion.yes_votes,
                no_votes=motion.no_votes,
                abstain_votes=motion.abstain_votes,
                passed=(motion.status == "passed"),
                voting_type=motion.voting_type,
            ),
        )

        action = "created" if created else "updated"
        msg = f"VoteResult {action} for motion {motion_pk}."
        logger.info(msg)
        return msg

    except Motion.DoesNotExist:
        logger.error("recalculate_vote_results: Motion %s not found.", motion_pk)
        return f"Error: Motion {motion_pk} not found."
    except Exception as exc:
        logger.error(
            "recalculate_vote_results error for motion %s: %s",
            motion_pk,
            exc,
            exc_info=True,
        )
        raise
