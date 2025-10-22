"""
Management command to clean up stale preview sessions.

Closes preview sessions that are in draft/ready/open state but haven't been
updated in a specified number of days (default: 7).

Usage:
    python manage.py cleanup_stale_previews
    python manage.py cleanup_stale_previews --days 14
    python manage.py cleanup_stale_previews --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from blog.models import PreviewSession


class Command(BaseCommand):
    help = 'Close stale preview sessions that are older than specified days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to consider a session stale (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be closed without actually closing'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        if days < 1:
            raise CommandError('--days must be at least 1')
        
        cutoff = timezone.now() - timedelta(days=days)
        
        # Find stale sessions in non-terminal states
        stale_sessions = PreviewSession.objects.filter(
            updated_at__lt=cutoff,
            status__in=['draft', 'ready', 'open']
        ).select_related('site')
        
        count = stale_sessions.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No stale sessions found (older than {days} days)'
            ))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would close {count} stale session(s):'
            ))
            for session in stale_sessions:
                age_days = (timezone.now() - session.updated_at).days
                self.stdout.write(
                    f'  - {session.uuid} (Site: {session.site.slug}, '
                    f'Status: {session.status}, Age: {age_days} days, '
                    f'PR: {session.pr_number or "N/A"})'
                )
        else:
            self.stdout.write(
                f'Closing {count} stale session(s) older than {days} days...'
            )
            
            closed_count = 0
            for session in stale_sessions:
                age_days = (timezone.now() - session.updated_at).days
                self.stdout.write(
                    f'  Closing {session.uuid} (Site: {session.site.slug}, '
                    f'Status: {session.status}, Age: {age_days} days)'
                )
                
                session.status = 'closed'
                session.save(update_fields=['status', 'updated_at'])
                closed_count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully closed {closed_count} stale session(s)'
            ))
