from decimal import Decimal
import re

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date


class WithdrawalService:
    @staticmethod
    def _to_date(value):
        if not value:
            return None
        if hasattr(value, 'year'):
            return value
        if isinstance(value, str):
            parsed = parse_date(value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _coerce_decimal(value, field_name='amount'):
        if value is None or value == '':
            raise ValueError(f"{field_name} is required")
        amount = Decimal(str(value))
        if amount <= 0:
            raise ValueError(f"{field_name} must be greater than 0")
        return amount

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return str(value.quantize(Decimal('0.01')))

    @staticmethod
    def _is_secretary(user) -> bool:
        membership = getattr(user, 'sacco_membership', None)
        if not membership:
            return False
        role = (membership.role or '').lower()
        return bool(membership.is_secretary or ('secretary' in role))

    @staticmethod
    def get_withdrawable_sections(sacco):
        from saccos.models import PassbookSection

        return PassbookSection.objects.filter(
            sacco=sacco,
            is_active=True,
            withdrawable=True,
        ).order_by('display_order', 'id')

    @staticmethod
    def get_reserved_amounts_by_section(member):
        from django.db.models import Sum
        from saccos.models import WithdrawalAllocation

        rows = WithdrawalAllocation.objects.filter(
            withdrawal__member=member,
            withdrawal__status__in=['pending', 'approved'],
        ).values('section_id').annotate(total=Sum('amount'))

        reserved = {}
        for r in rows:
            reserved[int(r['section_id'])] = r['total'] or Decimal('0')
        return reserved

    @staticmethod
    def get_available_summary(sacco, member):
        from saccos.services.passbook_service import PassbookService

        passbook = member.get_passbook()
        sections = list(WithdrawalService.get_withdrawable_sections(sacco))
        reserved_by_section = WithdrawalService.get_reserved_amounts_by_section(member)

        total_balance = Decimal('0')
        total_reserved = Decimal('0')
        total_available = Decimal('0')
        section_rows = []

        for section in sections:
            balance = PassbookService.get_section_balance(passbook, section)
            reserved = reserved_by_section.get(section.id, Decimal('0'))
            available = balance - reserved
            if available < 0:
                available = Decimal('0')

            total_balance += balance
            total_reserved += reserved
            total_available += available

            section_rows.append({
                'section_id': section.id,
                'section_name': section.name,
                'section_type': section.section_type,
                'color': section.color,
                'balance': WithdrawalService._format_decimal(balance),
                'reserved': WithdrawalService._format_decimal(reserved),
                'available': WithdrawalService._format_decimal(available),
            })

        return {
            'member_id': member.id,
            'total_balance': WithdrawalService._format_decimal(total_balance),
            'total_reserved': WithdrawalService._format_decimal(total_reserved),
            'total_available': WithdrawalService._format_decimal(total_available),
            'sections': section_rows,
        }

    @staticmethod
    def _generate_withdrawal_number(sacco):
        from saccos.models import SaccoWithdrawal

        prefix = sacco.registration_number or 'WD'
        last = SaccoWithdrawal.objects.filter(
            sacco=sacco,
            withdrawal_number__startswith=prefix,
        ).order_by('-id').first()

        if last:
            match = re.search(r'-(\d+)$', last.withdrawal_number)
            next_num = int(match.group(1)) + 1 if match else 1
        else:
            next_num = 1

        return f"{prefix}-{next_num:05d}"

    @staticmethod
    def _build_auto_allocations(sacco, member, amount: Decimal):
        from saccos.services.passbook_service import PassbookService

        passbook = member.get_passbook()
        reserved_by_section = WithdrawalService.get_reserved_amounts_by_section(member)
        sections = list(WithdrawalService.get_withdrawable_sections(sacco))

        remaining = amount
        allocations = []

        for section in sections:
            if remaining <= 0:
                break
            balance = PassbookService.get_section_balance(passbook, section)
            reserved = reserved_by_section.get(section.id, Decimal('0'))
            available = balance - reserved
            if available <= 0:
                continue

            take = min(available, remaining)
            if take > 0:
                allocations.append({'section': section, 'amount': take})
                remaining -= take

        if remaining > 0:
            raise ValueError('Insufficient withdrawable balance')

        return allocations

    @staticmethod
    @transaction.atomic
    def create_withdrawal_request(
        sacco,
        member,
        amount,
        requested_by,
        request_date=None,
        reason='',
        notes='',
        allocations=None,
    ):
        from saccos.models import SaccoWithdrawal, WithdrawalAllocation, PassbookSection

        amount = WithdrawalService._coerce_decimal(amount)

        request_date_obj = WithdrawalService._to_date(request_date) or timezone.now().date()

        summary = WithdrawalService.get_available_summary(sacco=sacco, member=member)
        total_available = Decimal(str(summary['total_available']))
        if amount > total_available:
            raise ValueError('Requested amount exceeds available withdrawable balance')

        withdrawal = SaccoWithdrawal.objects.create(
            sacco=sacco,
            member=member,
            withdrawal_number=WithdrawalService._generate_withdrawal_number(sacco),
            request_date=request_date_obj,
            amount=amount,
            reason=reason or '',
            notes=notes or '',
            status='pending',
            requested_by=requested_by if getattr(requested_by, 'id', None) else None,
        )

        if allocations:
            built = []
            total = Decimal('0')
            for row in allocations:
                section_id = row.get('section') or row.get('section_id')
                alloc_amount = WithdrawalService._coerce_decimal(row.get('amount'), field_name='allocation amount')
                section = PassbookSection.objects.get(id=section_id, sacco=sacco)
                if not section.withdrawable:
                    raise ValueError(f"Section '{section.name}' is not withdrawable")
                built.append({'section': section, 'amount': alloc_amount})
                total += alloc_amount

            if total != amount:
                raise ValueError('Allocation total must equal requested amount')
        else:
            built = WithdrawalService._build_auto_allocations(sacco=sacco, member=member, amount=amount)

        for row in built:
            WithdrawalAllocation.objects.create(
                withdrawal=withdrawal,
                section=row['section'],
                amount=row['amount'],
            )

        return withdrawal

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(withdrawal, approved_by, approval_date=None):
        if withdrawal.status != 'pending':
            raise ValueError(f"Cannot approve withdrawal with status: {withdrawal.status}")

        approval_date_obj = WithdrawalService._to_date(approval_date) or timezone.now().date()

        withdrawal.status = 'approved'
        withdrawal.approved_by = approved_by
        withdrawal.approval_date = approval_date_obj
        withdrawal.save()
        return withdrawal

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(withdrawal, rejected_by, rejection_reason=''):
        if withdrawal.status != 'pending':
            raise ValueError(f"Cannot reject withdrawal with status: {withdrawal.status}")

        withdrawal.status = 'rejected'
        withdrawal.approved_by = rejected_by
        withdrawal.rejection_reason = rejection_reason or ''
        withdrawal.save()
        return withdrawal

    @staticmethod
    @transaction.atomic
    def disburse_withdrawal(withdrawal, disbursement_date=None, recorded_by=None):
        from saccos.services.passbook_service import PassbookService
        from saccos.services.sacco_account_service import SaccoAccountService
        from common.enums import TransactionType, PaymentCategory

        if withdrawal.status != 'approved':
            raise ValueError(f"Cannot disburse withdrawal with status: {withdrawal.status}")

        disbursement_date_obj = WithdrawalService._to_date(disbursement_date) or timezone.now().date()

        passbook = withdrawal.member.get_passbook()

        allocations = list(withdrawal.allocations.select_related('section').all())
        if not allocations:
            raise ValueError('No allocations found for this withdrawal')

        for alloc in allocations:
            if not alloc.section.withdrawable:
                raise ValueError(f"Section '{alloc.section.name}' is not withdrawable")

        for alloc in allocations:
            entry = PassbookService.record_entry(
                passbook=passbook,
                section=alloc.section,
                amount=alloc.amount,
                transaction_type='debit',
                description=f"Withdrawal - {withdrawal.withdrawal_number}",
                recorded_by=recorded_by or withdrawal.approved_by,
                transaction_date=disbursement_date_obj,
                reference_number=withdrawal.withdrawal_number,
            )
            alloc.passbook_entry = entry
            alloc.save()

        sacco_account = withdrawal.sacco.get_or_create_account()
        SaccoAccountService.record_transaction(
            sacco_account=sacco_account,
            transaction_type=TransactionType.EXPENSE,
            amount=withdrawal.amount,
            category=PaymentCategory.SACCO_WITHDRAWAL,
            description=f"Withdrawal - {withdrawal.withdrawal_number} ({withdrawal.member.member_number})",
            date=disbursement_date_obj,
            recorded_by=recorded_by or withdrawal.approved_by,
        )

        withdrawal.status = 'disbursed'
        withdrawal.disbursement_date = disbursement_date_obj
        withdrawal.save()

        return withdrawal
