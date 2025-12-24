from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from common.enums import TransactionType, PaymentCategory
from saccos.services.sacco_account_service import SaccoAccountService


class Command(BaseCommand):
    help = 'Backfill SACCO account expense transactions for withdrawals that were already disbursed.'

    def add_arguments(self, parser):
        parser.add_argument('--sacco-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        from finance.models import Transaction
        from saccos.models import SaccoOrganization, SaccoWithdrawal

        sacco_id = options['sacco_id']
        dry_run = bool(options.get('dry_run'))

        sacco = SaccoOrganization.objects.get(id=sacco_id)
        sacco_account = sacco.get_or_create_account()
        account = sacco_account.account

        withdrawals = SaccoWithdrawal.objects.filter(
            sacco=sacco,
        ).filter(
            status='disbursed'
        )

        allocations_disbursed = SaccoWithdrawal.objects.filter(
            sacco=sacco,
            allocations__passbook_entry__isnull=False,
        )

        withdrawals = (withdrawals | allocations_disbursed).distinct().order_by('request_date', 'id')

        created = 0
        skipped = 0
        total_amount = Decimal('0')

        for withdrawal in withdrawals:
            exists = Transaction.objects.filter(
                account=account,
                category=PaymentCategory.SACCO_WITHDRAWAL,
                description__icontains=withdrawal.withdrawal_number,
            ).exists()

            if exists:
                skipped += 1
                continue

            date = withdrawal.disbursement_date or withdrawal.approval_date or withdrawal.request_date

            if not dry_run:
                SaccoAccountService.record_transaction(
                    sacco_account=sacco_account,
                    transaction_type=TransactionType.EXPENSE,
                    amount=withdrawal.amount,
                    category=PaymentCategory.SACCO_WITHDRAWAL,
                    description=f"Withdrawal - {withdrawal.withdrawal_number} ({withdrawal.member.member_number})",
                    date=date,
                    recorded_by=None,
                )

            created += 1
            total_amount += withdrawal.amount

        self.stdout.write(f"SACCO: {sacco.name} (id={sacco.id})")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Withdrawals matched: {withdrawals.count()}")
        self.stdout.write(f"Transactions to create: {created}")
        self.stdout.write(f"Transactions skipped (already exists): {skipped}")
        self.stdout.write(f"Total amount: {total_amount}")

        if dry_run:
            self.stdout.write('No changes made. Re-run without --dry-run to apply.')
