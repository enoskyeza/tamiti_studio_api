from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from common.enums import TransactionType
from saccos.services.passbook_service import PassbookService


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

    @transaction.atomic
    def handle(self, *args, **options):
        apply_changes = bool(options.get('apply'))
        sacco_id = options.get('sacco_id')
        member_id = options.get('member_id')
        passbook_id = options.get('passbook_id')
        section_id = options.get('section_id')
        skip_passbooks = bool(options.get('skip_passbooks'))
        skip_sacco_accounts = bool(options.get('skip_sacco_accounts'))

        summaries = {
            'apply_changes': apply_changes,
            'passbooks': None,
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
