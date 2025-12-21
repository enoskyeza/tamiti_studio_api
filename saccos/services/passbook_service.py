from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta


class PassbookService:
    """
    Business logic for passbook operations
    Phase 2: Passbook System
    """
    
    @staticmethod
    def create_passbook(member):
        """
        Create a passbook for a member
        
        Args:
            member: SaccoMember instance
            
        Returns:
            MemberPassbook instance
        """
        from saccos.models import MemberPassbook
        
        passbook = MemberPassbook.objects.create(
            member=member,
            sacco=member.sacco,
            passbook_number=member.passbook_number or member.member_number
        )
        return passbook
    
    @staticmethod
    @transaction.atomic
    def record_entry(
        passbook,
        section,
        amount,
        transaction_type,
        description,
        recorded_by,
        transaction_date=None,
        reference_number='',
        week_number=None,
        **kwargs
    ):
        """
        Record a single entry in the passbook
        
        Args:
            passbook: MemberPassbook instance
            section: PassbookSection instance
            amount: Transaction amount (Decimal)
            transaction_type: 'credit' or 'debit'
            description: Transaction description
            recorded_by: User who recorded this
            transaction_date: Date of transaction (defaults to today)
            reference_number: Optional reference
            week_number: Optional week number link
            **kwargs: Additional fields
        
        Returns:
            PassbookEntry instance
        """
        from saccos.models import PassbookEntry
        
        if not transaction_date:
            transaction_date = timezone.now().date()
        
        entry = PassbookEntry.objects.create(
            passbook=passbook,
            section=section,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            recorded_by=recorded_by,
            transaction_date=transaction_date,
            reference_number=reference_number,
            week_number=week_number,
            **kwargs
        )
        
        recalc_result = PassbookService.recalculate_section_running_balances_for_ids(
            passbook_id=passbook.id,
            section_id=section.id,
            apply_changes=True,
        )
        if recalc_result.get('entries_changed'):
            entry.refresh_from_db(fields=['balance_after'])

        return entry
    
    @staticmethod
    def get_section_balance(passbook, section):
        """
        Get current balance for a specific section
        
        Args:
            passbook: MemberPassbook instance
            section: PassbookSection instance
            
        Returns:
            Decimal: Current balance
        """
        return passbook.get_section_balance(section)
    
    @staticmethod
    def recalculate_section_running_balances_for_ids(passbook_id, section_id, apply_changes=True):
        from saccos.models import PassbookEntry

        entries = list(
            PassbookEntry.objects.filter(
                passbook_id=passbook_id,
                section_id=section_id,
            ).order_by('transaction_date', 'created_at', 'id')
        )

        running_balance = Decimal('0')
        changed = []
        for entry in entries:
            if entry.transaction_type == 'credit':
                running_balance += entry.amount
            else:
                running_balance -= entry.amount

            if entry.balance_after != running_balance:
                entry.balance_after = running_balance
                changed.append(entry)

        if apply_changes and changed:
            PassbookEntry.objects.bulk_update(changed, ['balance_after'])

        return {
            'entries_checked': len(entries),
            'entries_changed': len(changed),
        }
    
    @staticmethod
    def get_all_balances(passbook):
        """
        Get balances for all sections
        
        Args:
            passbook: MemberPassbook instance
            
        Returns:
            dict: {section_name: {'section_id', 'section_type', 'balance', 'color'}}
        """
        from saccos.models import PassbookSection
        
        sections = PassbookSection.objects.filter(
            sacco=passbook.sacco,
            is_active=True
        )
        
        balances = {}
        for section in sections:
            balances[section.name] = {
                'section_id': section.id,
                'section_type': section.section_type,
                'balance': PassbookService.get_section_balance(passbook, section),
                'color': section.color
            }
        
        return balances
    
    @staticmethod
    def generate_statement(
        passbook,
        start_date=None,
        end_date=None,
        section=None
    ):
        """
        Generate passbook statement for a date range
        
        Args:
            passbook: MemberPassbook instance
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)
            section: Optional specific PassbookSection
            
        Returns:
            dict: Statement data with sections, entries, and summary
        """
        from saccos.models import PassbookSection, PassbookEntry
        
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Get sections to include
        if section:
            sections = [section]
        else:
            sections = PassbookSection.objects.filter(
                sacco=passbook.sacco,
                is_active=True
            )
        
        statement = {
            'member': {
                'name': passbook.member.user.get_full_name(),
                'member_number': passbook.member.member_number,
                'passbook_number': passbook.passbook_number
            },
            'period': {
                'start': start_date,
                'end': end_date
            },
            'sections': []
        }
        
        total_credits = Decimal('0')
        total_debits = Decimal('0')
        
        for section_obj in sections:
            # Get opening balance (balance at start_date)
            opening_entry = PassbookEntry.objects.filter(
                passbook=passbook,
                section=section_obj,
                transaction_date__lt=start_date
            ).order_by('-transaction_date', '-created_at').first()
            
            opening_balance = opening_entry.balance_after if opening_entry else Decimal('0')
            
            # Get entries in period
            entries = PassbookEntry.objects.filter(
                passbook=passbook,
                section=section_obj,
                transaction_date__gte=start_date,
                transaction_date__lte=end_date
            ).order_by('transaction_date', 'created_at')
            
            # Calculate totals
            section_credits = sum(
                e.amount for e in entries if e.transaction_type == 'credit'
            )
            section_debits = sum(
                e.amount for e in entries if e.transaction_type == 'debit'
            )
            
            closing_balance = PassbookService.get_section_balance(passbook, section_obj)
            
            statement['sections'].append({
                'section': {
                    'id': section_obj.id,
                    'name': section_obj.name,
                    'type': section_obj.section_type,
                    'color': section_obj.color
                },
                'opening_balance': opening_balance,
                'entries': list(entries),
                'credits': section_credits,
                'debits': section_debits,
                'closing_balance': closing_balance
            })
            
            total_credits += section_credits
            total_debits += section_debits
        
        statement['summary'] = {
            'total_credits': total_credits,
            'total_debits': total_debits,
            'net_change': total_credits - total_debits
        }
        
        return statement
    
    @staticmethod
    def get_compulsory_deductions(sacco, date=None):
        """
        Get all compulsory deduction rules for a SACCO
        Used for calculating cash round deductions (Phase 3)
        
        Args:
            sacco: SaccoOrganization instance
            date: Date to check effectiveness (defaults to today)
            
        Returns:
            QuerySet: Active deduction rules
        """
        from saccos.models import DeductionRule
        
        rules = DeductionRule.objects.filter(
            sacco=sacco,
            is_active=True,
            applies_to='recipient'
        )
        
        if date:
            effective_rules = [r for r in rules if r.is_effective(date)]
            return effective_rules
        
        return list(rules)
    
    @staticmethod
    @transaction.atomic
    def reverse_entry(entry, recorded_by, reason):
        """
        Create a reversal entry for a passbook entry
        
        Args:
            entry: PassbookEntry to reverse
            recorded_by: User creating the reversal
            reason: Reason for reversal
            
        Returns:
            PassbookEntry: The reversal entry
        """
        # Create opposite transaction
        reversal_type = 'debit' if entry.transaction_type == 'credit' else 'credit'
        
        reversal = PassbookService.record_entry(
            passbook=entry.passbook,
            section=entry.section,
            amount=entry.amount,
            transaction_type=reversal_type,
            description=f"REVERSAL: {reason} (Original: {entry.description})",
            recorded_by=recorded_by,
            transaction_date=timezone.now().date(),
            is_reversal=True,
            reverses_entry=entry
        )
        
        return reversal
