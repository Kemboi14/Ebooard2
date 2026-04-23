"""
Management command to clean up expired audit trail entries.
Runs automatically via Celery beat or can be run manually.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.esignature.models import ESignatureAuditLog
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired audit trail entries based on retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process per batch',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size', 1000)
        
        self.stdout.write('Starting audit trail cleanup...')
        
        # Find expired logs that can be deleted
        expired_logs = ESignatureAuditLog.objects.filter(
            is_archived=False
        ).filter(
            retention_until__lt=timezone.now()
        )
        
        # Also find logs older than 7 years without explicit retention
        default_retention = timezone.now() - timezone.timedelta(days=7*365)
        old_logs = ESignatureAuditLog.objects.filter(
            is_archived=False,
            retention_until__isnull=True,
            timestamp__lt=default_retention
        )
        
        total_expired = expired_logs.count()
        total_old = old_logs.count()
        total_to_delete = total_expired + total_old
        
        self.stdout.write(f'Found {total_expired} expired logs with retention_until')
        self.stdout.write(f'Found {total_old} logs older than 7 years without retention')
        self.stdout.write(f'Total records to delete: {total_to_delete}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No records will be deleted'))
            return
        
        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS('No records to delete'))
            return
        
        # Delete in batches
        deleted_count = 0
        for logs_queryset in [expired_logs, old_logs]:
            offset = 0
            while True:
                batch = list(logs_queryset[offset:offset + batch_size])
                if not batch:
                    break
                
                # Archive before deletion
                for log in batch:
                    log.is_archived = True
                    log.archived_at = timezone.now()
                    log.save(update_fields=['is_archived', 'archived_at'])
                
                # Delete the batch
                ids_to_delete = [log.id for log in batch]
                deleted = ESignatureAuditLog.objects.filter(id__in=ids_to_delete).delete()
                deleted_count += deleted[0] if deleted else 0
                
                offset += batch_size
                self.stdout.write(f'Deleted {deleted_count} of {total_to_delete} records...')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {deleted_count} audit trail records'
            )
        )
