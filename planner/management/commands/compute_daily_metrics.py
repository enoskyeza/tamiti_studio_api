"""
Management command to compute daily productivity metrics and insights.
Run this as a daily cron job for automated productivity tracking.
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from users.models import User
from planner.services import ProductivityAnalyzer
from planner.models import DailyReview, ProductivityInsight


class Command(BaseCommand):
    help = 'Compute daily productivity metrics and generate insights for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to compute metrics for (YYYY-MM-DD). Defaults to yesterday.',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Compute metrics for specific user only',
        )
        parser.add_argument(
            '--generate-insights',
            action='store_true',
            help='Also generate productivity insights (requires more data)',
        )

    def handle(self, *args, **options):
        # Determine target date
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"Invalid date format: {options['date']}. Use YYYY-MM-DD.")
                )
                return
        else:
            # Default to yesterday
            target_date = timezone.now().date() - timedelta(days=1)

        self.stdout.write(f"Computing metrics for {target_date}")

        # Get users to process
        if options['user_id']:
            try:
                users = [User.objects.get(id=options['user_id'])]
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User with ID {options['user_id']} not found.")
                )
                return
        else:
            # Process all active users who have had some activity
            users = User.objects.filter(
                is_active=True,
                time_blocks__start__date=target_date
            ).distinct()

        processed_count = 0
        insights_count = 0

        for user in users:
            try:
                with transaction.atomic():
                    # Compute daily review metrics
                    analyzer = ProductivityAnalyzer(user)
                    review = analyzer.compute_daily_review(target_date)
                    
                    self.stdout.write(
                        f"✓ Computed metrics for {user.email}: "
                        f"{review.productivity_score}% productivity, "
                        f"{review.completion_rate}% completion rate"
                    )
                    processed_count += 1

                    # Generate insights if requested and user has enough data
                    if options['generate_insights']:
                        review_count = DailyReview.objects.filter(owner_user=user).count()
                        if review_count >= 7:  # Need at least 7 days of data
                            insights = analyzer.generate_productivity_insights()
                            insights_count += len(insights)
                            
                            self.stdout.write(
                                f"  ✓ Generated {len(insights)} insights for {user.email}"
                            )
                        else:
                            self.stdout.write(
                                f"  - Skipped insights for {user.email} "
                                f"(only {review_count} days of data)"
                            )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing {user.email}: {str(e)}")
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Processed {processed_count} users. "
                f"Generated {insights_count} insights."
            )
        )

        # Cleanup old insights (keep only last 30 days of data)
        cleanup_date = target_date - timedelta(days=30)
        deleted_insights = ProductivityInsight.objects.filter(
            valid_from__lt=cleanup_date
        ).delete()[0]
        
        if deleted_insights > 0:
            self.stdout.write(f"Cleaned up {deleted_insights} old insights.")
