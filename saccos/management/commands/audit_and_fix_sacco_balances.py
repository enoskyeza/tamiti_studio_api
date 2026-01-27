from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from common.enums import TransactionType, PaymentCategory
from saccos.services.passbook_service import PassbookService
from saccos.services.sacco_account_service import SaccoAccountService


class Command(BaseCommand):
    help = "Audit and optionally fix passbook running balances and SACCO account balances."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
        parser.add_argument('--sacco-id', type=int, default=None)
        parser.add_argument('--member-id', type=int, default=None)
        parser.add_argument('--passbook-id', type=int, default=None)
        parser.add_argument('--section-id', type=int, default=None)
        parser.add_argument('--skip-passbooks', action='store_true')
        parser.add_argument('--skip-sacco-accounts', action='store_true')
        parser.add_argument(
            '--backfill-sacco-transactions-from-passbooks',
            action='store_true',
            help='Create/link missing SACCO finance transactions for eligible passbook entries (non-meeting by default).',
        )
        parser.add_argument(
            '--include-withdrawals',
            action='store_true',
            help='Include passbook entries linked to withdrawals when backfilling (NOT recommended; may double count).',
        )
        parser.add_argument(
            '--include-loan-section',
            action='store_true',
            help='Include passbook entries in the loan section when backfilling.',
        )
        parser.add_argument(
            '--backfill-sacco-transactions-from-loans',
            action='store_true',
            help='Create missing SACCO finance transactions for loan disbursements.',
        )
        parser.add_argument(
            '--backfill-sacco-transactions-from-loan-payments',
            action='store_true',
            help='Create missing SACCO finance transactions for loan repayments.',
        )
        parser.add_argument(
            '--backfill-sacco-transactions-from-withdrawals',
            action='store_true',
            help='Create missing SACCO finance transactions for withdrawals (approved/disbursed).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply_changes = bool(options.get('apply'))
        sacco_id = options.get('sacco_id')
        member_id = options.get('member_id')
        passbook_id = options.get('passbook_id')
        section_id = options.get('section_id')
        skip_passbooks = bool(options.get('skip_passbooks'))
        skip_sacco_accounts = bool(options.get('skip_sacco_accounts'))
        backfill_sacco_transactions_from_passbooks = bool(options.get('backfill_sacco_transactions_from_passbooks'))
        include_withdrawals = bool(options.get('include_withdrawals'))
        include_loan_section = bool(options.get('include_loan_section'))
        backfill_sacco_transactions_from_loans = bool(options.get('backfill_sacco_transactions_from_loans'))
        backfill_sacco_transactions_from_loan_payments = bool(options.get('backfill_sacco_transactions_from_loan_payments'))
        backfill_sacco_transactions_from_withdrawals = bool(options.get('backfill_sacco_transactions_from_withdrawals'))

        summaries = {
            'apply_changes': apply_changes,
            'passbooks': None,
            'passbook_to_sacco_transactions': None,
            'loan_disbursements_to_sacco_transactions': None,
            'loan_payments_to_sacco_transactions': None,
            'withdrawals_to_sacco_transactions': None,
            'sacco_accounts': None,
        }

        if not skip_passbooks:
            summaries['passbooks'] = self._audit_and_fix_passbooks(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
                member_id=member_id,
                passbook_id=passbook_id,
                section_id=section_id,
            )

        if backfill_sacco_transactions_from_passbooks:
            summaries['passbook_to_sacco_transactions'] = self._backfill_sacco_transactions_from_passbooks(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
                member_id=member_id,
                passbook_id=passbook_id,
                section_id=section_id,
                include_withdrawals=include_withdrawals,
                include_loan_section=include_loan_section,
            )

        if backfill_sacco_transactions_from_loans:
            summaries['loan_disbursements_to_sacco_transactions'] = self._backfill_sacco_transactions_from_loans(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
                member_id=member_id,
            )

        if backfill_sacco_transactions_from_loan_payments:
            summaries['loan_payments_to_sacco_transactions'] = self._backfill_sacco_transactions_from_loan_payments(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
                member_id=member_id,
            )

        if backfill_sacco_transactions_from_withdrawals:
            summaries['withdrawals_to_sacco_transactions'] = self._backfill_sacco_transactions_from_withdrawals(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
                member_id=member_id,
            )

        if not skip_sacco_accounts:
            summaries['sacco_accounts'] = self._audit_and_fix_sacco_accounts(
                apply_changes=apply_changes,
                sacco_id=sacco_id,
            )

        if apply_changes:
            self.stdout.write(self.style.SUCCESS('Audit/fix complete (changes applied).'))
        else:
            self.stdout.write(self.style.WARNING('Audit complete (dry-run; no changes applied). Use --apply to write fixes.'))

        for key, value in summaries.items():
            self.stdout.write(f"- {key}: {value}")

    def _backfill_sacco_transactions_from_passbooks(
        self,
        *,
        apply_changes,
        sacco_id,
        member_id,
        passbook_id,
        section_id,
        include_withdrawals,
        include_loan_section,
    ):
        from saccos.models import PassbookEntry, WithdrawalAllocation
        from finance.models import Transaction

        supported_section_types = {
            'savings': PaymentCategory.SACCO_SAVINGS,
            'welfare': PaymentCategory.SACCO_WELFARE,
            'development': PaymentCategory.SACCO_DEVELOPMENT,
            'emergency': PaymentCategory.SACCO_EMERGENCY,
            'interest': PaymentCategory.SACCO_LOAN_REPAYMENT,
        }
        if include_loan_section:
            supported_section_types['loan'] = PaymentCategory.SACCO_LOAN_REPAYMENT

        qs = PassbookEntry.objects.select_related('passbook', 'passbook__member', 'passbook__sacco', 'section')

        if sacco_id:
            qs = qs.filter(passbook__sacco_id=sacco_id)
        if member_id:
            qs = qs.filter(passbook__member_id=member_id)
        if passbook_id:
            qs = qs.filter(passbook_id=passbook_id)
        if section_id:
            qs = qs.filter(section_id=section_id)

        qs = qs.filter(meeting__isnull=True)

        qs = qs.filter(sacco_transaction__isnull=True)

        qs = qs.filter(treasury_opt_out=False)

        qs = qs.filter(section__section_type__in=list(supported_section_types.keys()))

        withdrawal_entry_ids = set()
        if not include_withdrawals:
            withdrawal_allocations = WithdrawalAllocation.objects.exclude(passbook_entry_id__isnull=True)
            if sacco_id:
                withdrawal_allocations = withdrawal_allocations.filter(withdrawal__sacco_id=sacco_id)
            if member_id:
                withdrawal_allocations = withdrawal_allocations.filter(withdrawal__member_id=member_id)

            withdrawal_entry_ids = set(withdrawal_allocations.values_list('passbook_entry_id', flat=True))
            if withdrawal_entry_ids:
                qs = qs.exclude(id__in=withdrawal_entry_ids)

        totals = {
            'entries_considered': qs.count(),
            'entries_skipped_withdrawals': len(withdrawal_entry_ids) if not include_withdrawals else 0,
            'transactions_linked_existing': 0,
            'transactions_created': 0,
        }

        for entry in qs.iterator(chunk_size=500):
            sacco = entry.passbook.sacco
            sacco_account = sacco.get_or_create_account()

            category = supported_section_types.get(entry.section.section_type)
            if not category:
                continue

            txn_type = TransactionType.INCOME
            if entry.transaction_type == 'debit':
                txn_type = TransactionType.EXPENSE

            marker = f"PassbookEntry#{entry.id}"
            existing = Transaction.objects.filter(
                account=sacco_account.account,
                description__contains=marker,
            ).order_by('-created_at')

            if existing.exists():
                txn = existing.first()
                totals['transactions_linked_existing'] += 1
                if apply_changes:
                    entry.sacco_transaction = txn
                    entry.save(update_fields=['sacco_transaction'])
                continue

            if not apply_changes:
                totals['transactions_created'] += 1
                continue

            txn = SaccoAccountService.record_transaction(
                sacco_account=sacco_account,
                transaction_type=txn_type,
                amount=entry.amount,
                category=category,
                description=(
                    f"Passbook sync - {marker} - {entry.passbook.member.member_number} - "
                    f"{entry.section.name}: {entry.description}"
                ),
                date=entry.transaction_date,
                recorded_by=entry.recorded_by,
                is_automated=False,
            )
            entry.sacco_transaction = txn
            entry.save(update_fields=['sacco_transaction'])
            totals['transactions_created'] += 1

        return totals

    def _backfill_sacco_transactions_from_loans(self, *, apply_changes, sacco_id, member_id):
        from finance.models import Transaction
        from saccos.models import SaccoLoan

        qs = SaccoLoan.objects.select_related('sacco', 'member', 'approved_by')
        if sacco_id:
            qs = qs.filter(sacco_id=sacco_id)
        if member_id:
            qs = qs.filter(member_id=member_id)

        qs = qs.exclude(status__in=['pending', 'rejected'])
        qs = qs.exclude(disbursement_date__isnull=True)

        totals = {
            'loans_considered': qs.count(),
            'transactions_created': 0,
            'transactions_skipped_existing': 0,
        }

        for loan in qs.iterator(chunk_size=200):
            sacco_account = loan.sacco.get_or_create_account()
            marker = f"SaccoLoan#{loan.id}"

            exists = Transaction.objects.filter(
                account=sacco_account.account,
                category=PaymentCategory.SACCO_LOAN_DISBURSEMENT,
            ).filter(
                description__contains=marker,
            ).exists()
            if not exists:
                exists = Transaction.objects.filter(
                    account=sacco_account.account,
                    category=PaymentCategory.SACCO_LOAN_DISBURSEMENT,
                    description__icontains=loan.loan_number,
                ).exists()

            if exists:
                totals['transactions_skipped_existing'] += 1
                continue

            totals['transactions_created'] += 1
            if not apply_changes:
                continue

            SaccoAccountService.record_transaction(
                sacco_account=sacco_account,
                transaction_type=TransactionType.EXPENSE,
                amount=loan.principal_amount,
                category=PaymentCategory.SACCO_LOAN_DISBURSEMENT,
                description=f"Loan disbursement - {marker} - {loan.loan_number} ({loan.member.member_number})",
                date=loan.disbursement_date,
                related_loan=loan,
                recorded_by=loan.approved_by,
                is_automated=True,
            )

        return totals

    def _backfill_sacco_transactions_from_loan_payments(self, *, apply_changes, sacco_id, member_id):
        from finance.models import Transaction
        from saccos.models import LoanPayment

        qs = LoanPayment.objects.select_related('loan', 'loan__sacco', 'loan__member', 'recorded_by')
        if sacco_id:
            qs = qs.filter(loan__sacco_id=sacco_id)
        if member_id:
            qs = qs.filter(loan__member_id=member_id)

        totals = {
            'payments_considered': qs.count(),
            'transactions_created': 0,
            'transactions_skipped_existing': 0,
        }

        for payment in qs.iterator(chunk_size=500):
            loan = payment.loan
            sacco_account = loan.sacco.get_or_create_account()
            marker = f"LoanPayment#{payment.id}"

            exists = Transaction.objects.filter(
                account=sacco_account.account,
                category=PaymentCategory.SACCO_LOAN_REPAYMENT,
            ).filter(
                description__contains=marker,
            ).exists()
            if not exists:
                exists = Transaction.objects.filter(
                    account=sacco_account.account,
                    category=PaymentCategory.SACCO_LOAN_REPAYMENT,
                    description__icontains=loan.loan_number,
                    amount=payment.total_amount,
                    date=payment.payment_date,
                ).exists()

            if exists:
                totals['transactions_skipped_existing'] += 1
                continue

            totals['transactions_created'] += 1
            if not apply_changes:
                continue

            SaccoAccountService.record_transaction(
                sacco_account=sacco_account,
                transaction_type=TransactionType.INCOME,
                amount=payment.total_amount,
                category=PaymentCategory.SACCO_LOAN_REPAYMENT,
                description=f"Loan repayment - {marker} - {loan.loan_number} ({loan.member.member_number})",
                date=payment.payment_date,
                related_loan=loan,
                recorded_by=payment.recorded_by,
                is_automated=True,
            )

        return totals

    def _backfill_sacco_transactions_from_withdrawals(self, *, apply_changes, sacco_id, member_id):
        from finance.models import Transaction
        from saccos.models import SaccoWithdrawal

        qs = SaccoWithdrawal.objects.select_related('sacco', 'member', 'approved_by')
        if sacco_id:
            qs = qs.filter(sacco_id=sacco_id)
        if member_id:
            qs = qs.filter(member_id=member_id)

        qs = qs.exclude(status__in=['pending', 'rejected'])

        totals = {
            'withdrawals_considered': qs.count(),
            'transactions_created': 0,
            'transactions_skipped_existing': 0,
        }

        for withdrawal in qs.iterator(chunk_size=200):
            sacco_account = withdrawal.sacco.get_or_create_account()

            exists = Transaction.objects.filter(
                account=sacco_account.account,
                category=PaymentCategory.SACCO_WITHDRAWAL,
                description__icontains=withdrawal.withdrawal_number,
            ).exists()

            if exists:
                totals['transactions_skipped_existing'] += 1
                continue

            totals['transactions_created'] += 1
            if not apply_changes:
                continue

            date = withdrawal.disbursement_date or withdrawal.approval_date or withdrawal.request_date
            SaccoAccountService.record_transaction(
                sacco_account=sacco_account,
                transaction_type=TransactionType.EXPENSE,
                amount=withdrawal.amount,
                category=PaymentCategory.SACCO_WITHDRAWAL,
                description=f"Withdrawal - {withdrawal.withdrawal_number} ({withdrawal.member.member_number})",
                date=date,
                recorded_by=withdrawal.approved_by,
                is_automated=True,
            )

        return totals

    def _audit_and_fix_passbooks(self, *, apply_changes, sacco_id, member_id, passbook_id, section_id):
        from saccos.models import MemberPassbook, PassbookEntry

        passbooks = MemberPassbook.objects.all()
        if sacco_id:
            passbooks = passbooks.filter(sacco_id=sacco_id)
        if member_id:
            passbooks = passbooks.filter(member_id=member_id)
        if passbook_id:
            passbooks = passbooks.filter(id=passbook_id)

        passbook_ids = list(passbooks.values_list('id', flat=True))
        if not passbook_ids:
            return {
                'passbooks_matched': 0,
                'sections_checked': 0,
                'entries_checked': 0,
                'entries_changed': 0,
            }

        entry_pairs = PassbookEntry.objects.filter(passbook_id__in=passbook_ids)
        if section_id:
            entry_pairs = entry_pairs.filter(section_id=section_id)

        pairs = list(entry_pairs.values_list('passbook_id', 'section_id').distinct())

        totals = {
            'passbooks_matched': len(passbook_ids),
            'sections_checked': 0,
            'entries_checked': 0,
            'entries_changed': 0,
        }

        for pb_id, sec_id in pairs:
            result = PassbookService.recalculate_section_running_balances_for_ids(
                passbook_id=pb_id,
                section_id=sec_id,
                apply_changes=apply_changes,
            )
            totals['sections_checked'] += 1
            totals['entries_checked'] += int(result.get('entries_checked') or 0)
            totals['entries_changed'] += int(result.get('entries_changed') or 0)

        return totals

    def _audit_and_fix_sacco_accounts(self, *, apply_changes, sacco_id):
        from saccos.models import SaccoAccount
        from finance.models import Transaction

        sacco_accounts = SaccoAccount.objects.select_related('account', 'sacco')
        if sacco_id:
            sacco_accounts = sacco_accounts.filter(sacco_id=sacco_id)

        checked = 0
        changed = 0

        for sacco_account in sacco_accounts:
            account = sacco_account.account
            if not account:
                continue

            checked += 1
            qs = Transaction.objects.filter(account=account)

            income_amount = qs.filter(type=TransactionType.INCOME).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            income_charges = qs.filter(type=TransactionType.INCOME).aggregate(total=Sum('transaction_charge'))['total'] or Decimal('0')
            expense_amount = qs.filter(type=TransactionType.EXPENSE).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            expense_charges = qs.filter(type=TransactionType.EXPENSE).aggregate(total=Sum('transaction_charge'))['total'] or Decimal('0')

            expected_balance = (income_amount - income_charges) - (expense_amount + expense_charges)

            if account.balance != expected_balance:
                changed += 1
                if apply_changes:
                    account.balance = expected_balance
                    account.save(update_fields=['balance'])

        return {
            'sacco_accounts_checked': checked,
            'sacco_accounts_changed': changed,
        }
