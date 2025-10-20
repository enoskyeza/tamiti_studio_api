from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from common.enums import TransactionType, PaymentCategory
from datetime import timedelta


class WeeklyMeetingService:
    """
    Business logic for weekly meetings and cash rounds
    Phase 3: Weekly Meetings
    
    CRITICAL: Implements CORRECTED deduction logic where only the
    cash round recipient pays compulsory deductions
    """
    
    @staticmethod
    @transaction.atomic
    def create_meeting(
        sacco,
        meeting_date,
        cash_round_recipient,
        recorded_by,
        notes=''
    ):
        """
        Create a new weekly meeting
        
        Args:
            sacco: SaccoOrganization instance
            meeting_date: Date of meeting
            cash_round_recipient: SaccoMember who receives this week
            recorded_by: User creating the meeting
            notes: Optional notes
            
        Returns:
            WeeklyMeeting instance
        """
        from saccos.models import WeeklyMeeting
        
        # Calculate week number and year
        week_number = meeting_date.isocalendar()[1]
        year = meeting_date.year
        
        meeting = WeeklyMeeting.objects.create(
            sacco=sacco,
            meeting_date=meeting_date,
            week_number=week_number,
            year=year,
            cash_round_recipient=cash_round_recipient,
            recorded_by=recorded_by,
            notes=notes,
            status='planned'
        )
        
        return meeting
    
    @staticmethod
    @transaction.atomic
    def record_contribution(
        meeting,
        member,
        amount_contributed,
        optional_savings=Decimal('0'),
        was_present=True,
        notes=''
    ):
        """
        Record a member's contribution to a weekly meeting
        
        Args:
            meeting: WeeklyMeeting instance
            member: SaccoMember instance
            amount_contributed: Total amount member brought
            optional_savings: Optional savings amount
            was_present: Whether member was present
            notes: Optional notes
            
        Returns:
            WeeklyContribution instance
        """
        from saccos.models import WeeklyContribution
        
        # Check if this member is the recipient
        is_recipient = (member == meeting.cash_round_recipient)
        
        contribution = WeeklyContribution.objects.create(
            meeting=meeting,
            member=member,
            was_present=was_present,
            amount_contributed=amount_contributed,
            optional_savings=optional_savings,
            is_recipient=is_recipient,
            notes=notes
        )
        
        return contribution
    
    @staticmethod
    @transaction.atomic
    def process_weekly_deductions(meeting, recorded_by):
        """
        Process deductions for the cash round recipient ONLY
        
        CRITICAL: This implements the CORRECTED business logic where
        only the recipient pays compulsory deductions, not all members.
        
        Args:
            meeting: WeeklyMeeting instance
            recorded_by: User processing deductions
            
        Returns:
            dict with created entries and totals
        """
        from saccos.models import PassbookSection, DeductionRule
        from saccos.services.passbook_service import PassbookService
        
        if not meeting.cash_round_recipient:
            return {
                'success': False,
                'error': 'No cash round recipient set for this meeting'
            }
        
        recipient = meeting.cash_round_recipient
        passbook = recipient.get_passbook()
        
        # Get deduction rules for this SACCO
        deduction_rules = DeductionRule.objects.filter(
            sacco=meeting.sacco,
            is_active=True,
            applies_to='recipient'
        )
        
        # Filter to only effective rules
        effective_rules = [r for r in deduction_rules if r.is_effective(meeting.meeting_date)]
        
        entries_created = []
        total_deductions = Decimal('0')
        
        # 1. Process RECIPIENT's compulsory deductions ONLY
        for rule in effective_rules:
            entry = PassbookService.record_entry(
                passbook=passbook,
                section=rule.section,
                amount=rule.amount,
                transaction_type='credit',
                description=f'Compulsory deduction - Week {meeting.week_number}',
                recorded_by=recorded_by,
                transaction_date=meeting.meeting_date,
                week_number=meeting.week_number,
                meeting=meeting
            )
            entries_created.append(entry)
            total_deductions += rule.amount
        
        # Update recipient's contribution with deductions
        recipient_contribution = meeting.contributions.filter(member=recipient).first()
        if recipient_contribution:
            # Map deductions to specific fields based on section type
            for rule in effective_rules:
                if rule.section.section_type == 'savings':
                    recipient_contribution.compulsory_savings_deduction = rule.amount
                elif rule.section.section_type == 'welfare':
                    recipient_contribution.welfare_deduction = rule.amount
                elif rule.section.section_type == 'development':
                    recipient_contribution.development_deduction = rule.amount
                else:
                    recipient_contribution.other_deductions += rule.amount
            
            recipient_contribution.calculate_total_deductions()
            recipient_contribution.save()
        
        # 2. Process ALL members' optional savings (not just recipient)
        try:
            optional_savings_section = PassbookSection.objects.get(
                sacco=meeting.sacco,
                section_type='savings',
                name='Optional Savings'
            )
            
            for contribution in meeting.contributions.filter(optional_savings__gt=0):
                member_passbook = contribution.member.get_passbook()
                
                entry = PassbookService.record_entry(
                    passbook=member_passbook,
                    section=optional_savings_section,
                    amount=contribution.optional_savings,
                    transaction_type='credit',
                    description=f'Optional savings - Week {meeting.week_number}',
                    recorded_by=recorded_by,
                    transaction_date=meeting.meeting_date,
                    week_number=meeting.week_number,
                    meeting=meeting
                )
                entries_created.append(entry)
        
        except PassbookSection.DoesNotExist:
            pass  # No optional savings section configured
        
        # 3. Recalculate meeting totals
        meeting.calculate_totals()
        
        return {
            'success': True,
            'entries_created': len(entries_created),
            'total_deductions': total_deductions,
            'recipient': recipient.member_number,
            'amount_to_bank': meeting.amount_to_bank,
            'amount_to_recipient': meeting.amount_to_recipient
        }
    
    @staticmethod
    @transaction.atomic
    def complete_meeting(meeting, recorded_by):
        """
        Mark meeting as completed and record SACCO account transaction
        
        This properly accounts for:
        1. Extra payments recorded BEFORE finalization (already in passbook)
        2. Deductions created DURING finalization
        3. All amounts sent to bank
        
        Args:
            meeting: WeeklyMeeting instance
            recorded_by: User completing the meeting
            
        Returns:
            Updated meeting
        """
        from saccos.services.sacco_account_service import SaccoAccountService
        from saccos.models import PassbookEntry
        
        meeting.status = 'completed'
        meeting.completed_at = timezone.now()
        meeting.recorded_by = recorded_by
        meeting.save()  # Save status first
        
        # CRITICAL: Recalculate totals AFTER status is 'completed'
        # This ensures calculate_totals() uses passbook entries as source of truth
        meeting.calculate_totals()
        
        # Calculate actual amount sent to bank by summing all passbook entries for this meeting
        # This includes:
        # - Extras recorded before finalization
        # - Compulsory deductions from recipient (created during finalization)
        # - Optional savings from all members
        meeting_entries = PassbookEntry.objects.filter(
            meeting=meeting,
            transaction_type='credit'  # All savings are credits to member accounts
        )
        
        actual_amount_to_bank = sum(
            entry.amount for entry in meeting_entries
        )
        
        # Get or create SACCO account and record the transaction
        try:
            sacco_account = meeting.sacco.get_or_create_account()
            
            # Record income transaction for amount sent to bank
            if actual_amount_to_bank > 0:
                SaccoAccountService.record_transaction(
                    sacco_account=sacco_account,
                    transaction_type=TransactionType.INCOME,
                    amount=actual_amount_to_bank,
                    category=PaymentCategory.SACCO_SAVINGS,
                    description=f"Week {meeting.week_number} - Member Savings",
                    date=meeting.meeting_date,
                    related_meeting=meeting,
                    recorded_by=recorded_by
                )
        except Exception as e:
            # Log error but don't fail meeting completion
            print(f"Error recording SACCO account transaction: {e}")
        
        # Advance cash round schedule to next member
        schedule = meeting.sacco.cash_round_schedules.filter(is_active=True).first()
        if schedule:
            schedule.advance_to_next_member()
        
        return meeting
    
    @staticmethod
    def create_cash_round_schedule(sacco, member_ids, start_date):
        """
        Create a new cash round schedule
        
        Args:
            sacco: SaccoOrganization instance
            member_ids: List of member IDs in rotation order
            start_date: When schedule starts
            
        Returns:
            CashRoundSchedule instance
        """
        from saccos.models import CashRoundSchedule
        
        # Deactivate old schedules
        CashRoundSchedule.objects.filter(
            sacco=sacco,
            is_active=True
        ).update(is_active=False, end_date=timezone.now().date())
        
        # Create new schedule
        schedule = CashRoundSchedule.objects.create(
            sacco=sacco,
            start_date=start_date,
            rotation_order=member_ids,
            current_position=0,
            is_active=True
        )
        
        return schedule
    
    @staticmethod
    def get_meeting_summary(meeting):
        """
        Get comprehensive summary of a meeting
        
        Args:
            meeting: WeeklyMeeting instance
            
        Returns:
            dict with all meeting details
        """
        contributions = meeting.contributions.all()
        
        return {
            'meeting': {
                'id': meeting.id,
                'date': meeting.meeting_date,
                'week_number': meeting.week_number,
                'year': meeting.year,
                'status': meeting.status
            },
            'cash_round': {
                'recipient': {
                    'member_number': meeting.cash_round_recipient.member_number if meeting.cash_round_recipient else None,
                    'name': meeting.cash_round_recipient.user.get_full_name() if meeting.cash_round_recipient else None
                },
                'amount_to_recipient': meeting.amount_to_recipient,
                'amount_to_bank': meeting.amount_to_bank,
                'total_deductions': meeting.total_deductions
            },
            'totals': {
                'total_collected': meeting.total_collected,
                'members_present': meeting.members_present,
                'members_absent': meeting.members_absent
            },
            'contributions': [
                {
                    'member_number': c.member.member_number,
                    'member_name': c.member.user.get_full_name(),
                    'was_present': c.was_present,
                    'amount_contributed': c.amount_contributed,
                    'optional_savings': c.optional_savings,
                    'is_recipient': c.is_recipient,
                    'total_deductions': c.total_deductions if c.is_recipient else 0
                }
                for c in contributions
            ]
        }
