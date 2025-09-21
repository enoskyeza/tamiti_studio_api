from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import User


class Command(BaseCommand):
    help = 'Clean up expired temporary users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=0,
            help='Delete users expired more than N days ago (default: 0 for immediate)',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff_time = now - timedelta(days=options['days'])
        
        expired_users = User.objects.filter(
            is_temporary=True,
            expires_at__lt=cutoff_time
        )
        
        count = expired_users.count()
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'Would delete {count} expired temporary users')
            )
            for user in expired_users[:10]:  # Show first 10
                self.stdout.write(f'  - {user.username} (expired: {user.expires_at})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            if count > 0:
                expired_users.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {count} expired temporary users')
                )
            else:
                self.stdout.write('No expired temporary users found')
