"""
Management command to archive records based on retention policies.
Handles archiving of meeting minutes, compliance records, user archives, and other data.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import User, UserArchive
from apps.meetings.models import MeetingMinutes
from apps.risk.models import ComplianceArchive, ComplianceAttendance
from apps.policy.models import PolicyExpiryMonitor
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Archive records based on retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually archiving',
        )
        parser.add_argument(
            '--record-type',
            type=str,
            choices=['all', 'users', 'minutes', 'compliance', 'policies'],
            default='all',
            help='Type of records to archive',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        record_type = options.get('record_type', 'all')
        
        self.stdout.write(f'Starting archival process for: {record_type}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No records will be archived'))
        
        total_archived = 0
        
        if record_type in ['all', 'users']:
            total_archived += self.archive_users(dry_run)
        
        if record_type in ['all', 'minutes']:
            total_archived += self.archive_meeting_minutes(dry_run)
        
        if record_type in ['all', 'compliance']:
            total_archived += self.archive_compliance_records(dry_run)
        
        if record_type in ['all', 'policies']:
            total_archived += self.archive_policy_records(dry_run)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Archival process complete. Total records archived: {total_archived}'
            )
        )
    
    def archive_users(self, dry_run):
        """Archive soft-deleted users"""
        self.stdout.write('Processing user archiving...')
        
        # Find soft-deleted users that haven't been archived yet
        deleted_users = User.objects.filter(
            is_deleted=True,
            deleted_at__isnull=False
        ).exclude(
            id__in=UserArchive.objects.values_list('original_user_id', flat=True)
        )
        
        count = deleted_users.count()
        self.stdout.write(f'Found {count} users to archive')
        
        if dry_run or count == 0:
            return count
        
        archived_count = 0
        for user in deleted_users:
            # Create archive record
            archive = UserArchive.objects.create(
                original_user_id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user.role,
                termination_reason='account_terminated',
                termination_notes=f'User soft-deleted on {user.deleted_at}',
                terminated_by=user.deleted_by,
                archived_data={
                    'phone_number': user.phone_number,
                    'department': user.department,
                    'job_title': user.job_title,
                    'board_position': user.board_position,
                }
            )
            archived_count += 1
        
        self.stdout.write(f'Archived {archived_count} users')
        return archived_count
    
    def archive_meeting_minutes(self, dry_run):
        """Archive meeting minutes based on retention policy"""
        self.stdout.write('Processing meeting minutes archiving...')
        
        # Find meeting minutes that should be archived based on retention period
        retention_date = timezone.now() - timedelta(days=7*365)  # 7 years
        
        minutes_to_archive = MeetingMinutes.objects.filter(
            is_archived=False,
            published_at__isnull=False,
            published_at__lt=retention_date
        )
        
        count = minutes_to_archive.count()
        self.stdout.write(f'Found {count} meeting minutes to archive')
        
        if dry_run or count == 0:
            return count
        
        archived_count = 0
        for minutes in minutes_to_archive:
            minutes.is_archived = True
            minutes.archive_date = timezone.now()
            minutes.save(update_fields=['is_archived', 'archive_date'])
            archived_count += 1
        
        self.stdout.write(f'Archived {archived_count} meeting minutes')
        return archived_count
    
    def archive_compliance_records(self, dry_run):
        """Archive compliance attendance records"""
        self.stdout.write('Processing compliance record archiving...')
        
        retention_date = timezone.now() - timedelta(days=7*365)
        
        # Archive old compliance attendance records
        old_attendance = ComplianceAttendance.objects.filter(
            recorded_at__lt=retention_date
        )
        
        count = old_attendance.count()
        self.stdout.write(f'Found {count} compliance attendance records to archive')
        
        if dry_run or count == 0:
            return count
        
        archived_count = 0
        for attendance in old_attendance:
            # Create archive record
            archive = ComplianceArchive.objects.create(
                record_type='compliance_attendance',
                original_record_id=attendance.id,
                record_title=f'Compliance Attendance - {attendance.user.get_full_name()}',
                compliance_category=attendance.compliance_type,
                archived_data={
                    'user_id': str(attendance.user.id),
                    'user_email': attendance.user.email,
                    'user_name': attendance.user.get_full_name(),
                    'meeting_id': str(attendance.meeting.id) if attendance.meeting else None,
                    'attendance_status': attendance.attendance_status,
                    'is_excused': attendance.is_excused,
                    'check_in_time': attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                    'check_out_time': attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                },
                archived_by=attendance.recorded_by,
                archive_reason='Retention period expired'
            )
            archived_count += 1
        
        self.stdout.write(f'Archived {archived_count} compliance records')
        return archived_count
    
    def archive_policy_records(self, dry_run):
        """Archive expired policy monitoring records"""
        self.stdout.write('Processing policy record archiving...')
        
        # Archive expired policy monitors
        expired_monitors = PolicyExpiryMonitor.objects.filter(
            is_expired=True,
            is_resolved=True
        )
        
        count = expired_monitors.count()
        self.stdout.write(f'Found {count} expired policy monitors to archive')
        
        if dry_run or count == 0:
            return count
        
        archived_count = 0
        for monitor in expired_monitors:
            # Mark as archived by updating status
            monitor.archive_status = 'expired'
            monitor.save(update_fields=['archive_status'])
            archived_count += 1
        
        self.stdout.write(f'Archived {archived_count} policy records')
        return archived_count
