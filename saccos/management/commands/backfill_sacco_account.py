"""
Management command to backfill SACCO account transactions from existing meetings
This will create transactions for all completed meetings that were finalized before
the SACCO account feature was implemented.

Usage:
    python manage.py backfill_sacco_account --sacco_id=1
    python manage.py backfill_sacco_account --sacco_id=1 --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from saccos.models import SaccoOrganization, WeeklyMeeting, PassbookEntry, SaccoAccount
from saccos.services.sacco_account_service import SaccoAccountService
from common.enums import TransactionType, PaymentCategory
from finance.models import Transaction


class Command(BaseCommand):
    help = 'Backfill SACCO account transactions from existing completed meetings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sacco_id',
            type=int,
            help='SACCO ID to backfill (required)',
            required=True
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to see what would be updated'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        sacco_id = options['sacco_id']
        dry_run = options['dry_run']

        self.stdout.write(self.style.WARNING(f'\n{"="*60}'))
        self.stdout.write(self.style.WARNING(f'SACCO Account Backfill Script'))
        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))

        # Get SACCO
        try:
            sacco = SaccoOrganization.objects.get(id=sacco_id)
            self.stdout.write(f'SACCO: {sacco.name}\n')
        except SaccoOrganization.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'SACCO with ID {sacco_id} not found'))
            return

        # Get or create SACCO account
        try:
            sacco_account = sacco.get_or_create_account()
            self.stdout.write(f'SACCO Account: {sacco_account.account.name}')
            self.stdout.write(f'Current Balance: UGX {sacco_account.current_balance:,.2f}\n')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting SACCO account: {e}'))
            return

        # Find all completed meetings
        completed_meetings = WeeklyMeeting.objects.filter(
            sacco=sacco,
            status='completed'
        ).order_by('meeting_date')

        self.stdout.write(f'Found {completed_meetings.count()} completed meetings\n')

        if not completed_meetings.exists():
            self.stdout.write(self.style.WARNING('No completed meetings found. Nothing to backfill.'))
            return

        # Check which meetings already have transactions
        existing_transaction_meetings = set()
        existing_transactions = Transaction.objects.filter(
            account=sacco_account.account,
            category=PaymentCategory.SACCO_SAVINGS
        )

        for txn in existing_transactions:
            # Extract meeting reference from description
            if '[Meeting #' in txn.description:
                existing_transaction_meetings.add(txn.description)

        self.stdout.write(f'Existing transactions: {len(existing_transaction_meetings)}\n')
        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))

        # Process each meeting
        total_amount = Decimal('0')
        meetings_processed = 0
        meetings_skipped = 0

        for meeting in completed_meetings:
            meeting_ref = f'[Meeting #{meeting.week_number}, {meeting.year}]'
            
            # Skip if transaction already exists
            if any(meeting_ref in desc for desc in existing_transaction_meetings):
                meetings_skipped += 1
                self.stdout.write(
                    self.style.WARNING(f'⏭️  Week {meeting.week_number} ({meeting.meeting_date}) - Already processed')
                )
                continue

            # Get all passbook entries for this meeting (credits = savings)
            meeting_entries = PassbookEntry.objects.filter(
                meeting=meeting,
                transaction_type='credit'
            )

            # Calculate total amount sent to bank
            amount_to_bank = sum(entry.amount for entry in meeting_entries)

            if amount_to_bank == 0:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Week {meeting.week_number} ({meeting.meeting_date}) - No savings recorded')
                )
                continue

            # Show what will be created
            self.stdout.write(
                f'✅ Week {meeting.week_number} ({meeting.meeting_date}): '
                f'UGX {amount_to_bank:,.2f} ({meeting_entries.count()} entries)'
            )

            if not dry_run:
                # Create transaction
                try:
                    SaccoAccountService.record_transaction(
                        sacco_account=sacco_account,
                        transaction_type=TransactionType.INCOME,
                        amount=amount_to_bank,
                        category=PaymentCategory.SACCO_SAVINGS,
                        description=f'Week {meeting.week_number} - Member Savings (Backfilled)',
                        date=meeting.meeting_date,
                        related_meeting=meeting,
                        recorded_by=None
                    )
                    meetings_processed += 1
                    total_amount += amount_to_bank
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'   Error creating transaction: {e}')
                    )
            else:
                meetings_processed += 1
                total_amount += amount_to_bank

        # Summary
        self.stdout.write(self.style.WARNING(f'\n{"="*60}'))
        self.stdout.write(self.style.WARNING('SUMMARY'))
        self.stdout.write(self.style.WARNING(f'{"="*60}'))
        self.stdout.write(f'Total meetings found: {completed_meetings.count()}')
        self.stdout.write(f'Already processed: {meetings_skipped}')
        self.stdout.write(f'Newly processed: {meetings_processed}')
        self.stdout.write(f'Total amount: UGX {total_amount:,.2f}')

        if not dry_run:
            # Refresh account to get updated balance
            sacco_account.refresh_from_db()
            sacco_account.account.refresh_from_db()
            self.stdout.write(f'\nNew SACCO Account Balance: UGX {sacco_account.current_balance:,.2f}')
            self.stdout.write(self.style.SUCCESS('\n✅ Backfill completed successfully!'))
        else:
            expected_balance = sacco_account.current_balance + total_amount
            self.stdout.write(f'\nExpected Balance After Backfill: UGX {expected_balance:,.2f}')
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN - No changes made. Remove --dry-run to apply.'))

        self.stdout.write(self.style.WARNING(f'{"="*60}\n'))
