"""
Cash Round Service
Handles business logic for cash round management
"""
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from saccos.models import CashRound, CashRoundMember, CashRoundSchedule, SaccoOrganization, SaccoMember


class CashRoundService:
    """
    Service for managing cash rounds
    """
    
    @staticmethod
    @transaction.atomic
    def create_cash_round(sacco, name, start_date, weekly_amount, member_ids, created_by=None, notes=''):
        """
        Create a new cash round with members
        
        Args:
            sacco: SaccoOrganization instance
            name: Name of the cash round
            start_date: Date when round starts
            weekly_amount: Amount each member contributes per week
            member_ids: List of member IDs to include in this round
            created_by: User who created the round
            notes: Optional notes
            
        Returns:
            CashRound instance
        """
        print("\n" + "="*50)
        print("=== SERVICE: create_cash_round ===")
        print("="*50)
        print(f"SACCO: {sacco}")
        print(f"Name: {name}")
        print(f"Start Date: {start_date} (type: {type(start_date)})")
        print(f"Weekly Amount: {weekly_amount} (type: {type(weekly_amount)})")
        print(f"Member IDs: {member_ids}")
        print(f"Created By: {created_by}")
        print(f"Notes: {notes}")
        
        # Get next round number for this SACCO
        last_round = CashRound.objects.filter(sacco=sacco).order_by('-round_number').first()
        round_number = (last_round.round_number + 1) if last_round else 1
        print(f"Round Number: {round_number}")
        
        # Calculate expected end date (num_weeks = num_members)
        num_members = len(member_ids)
        print(f"Number of members: {num_members}")
        print(f"About to calculate: {start_date} + timedelta(weeks={num_members})")
        
        try:
            expected_end_date = start_date + timedelta(weeks=num_members)
            print(f"Expected end date: {expected_end_date}")
        except Exception as e:
            print(f"ERROR calculating end date: {type(e).__name__}: {str(e)}")
            raise
        
        # Create the cash round
        cash_round = CashRound.objects.create(
            sacco=sacco,
            name=name,
            round_number=round_number,
            start_date=start_date,
            expected_end_date=expected_end_date,
            weekly_amount=Decimal(str(weekly_amount)),
            num_weeks=num_members,
            status='planned',
            created_by=created_by,
            notes=notes
        )
        
        # Add members to the round
        for position, member_id in enumerate(member_ids):
            CashRoundMember.objects.create(
                cash_round=cash_round,
                member_id=member_id,
                position_in_rotation=position,
                is_active=True
            )
        
        # NOTE: Schedule is NOT automatically created
        # Users must explicitly create and set rotation order via the "Create Schedule" modal
        # This ensures conscious decision about payout order
        
        return cash_round
    
    @staticmethod
    @transaction.atomic
    def start_cash_round(cash_round):
        """
        Start a planned cash round
        
        Args:
            cash_round: CashRound instance
            
        Returns:
            Updated CashRound instance
        """
        if cash_round.status != 'planned':
            raise ValueError(f"Cannot start cash round with status '{cash_round.status}'")
        
        cash_round.start_round()
        
        # Activate the schedule
        if hasattr(cash_round, 'schedule'):
            cash_round.schedule.is_active = True
            cash_round.schedule.save()
        
        return cash_round
    
    @staticmethod
    @transaction.atomic
    def complete_cash_round(cash_round):
        """
        Mark a cash round as completed
        
        Args:
            cash_round: CashRound instance
            
        Returns:
            Updated CashRound instance
        """
        if cash_round.status != 'active':
            raise ValueError(f"Cannot complete cash round with status '{cash_round.status}'")
        
        cash_round.complete_round()
        
        # Deactivate the schedule
        if hasattr(cash_round, 'schedule'):
            cash_round.schedule.is_active = False
            cash_round.schedule.end_date = timezone.now().date()
            cash_round.schedule.save()
        
        return cash_round
    
    @staticmethod
    @transaction.atomic
    def add_member_to_round(cash_round, member, position=None):
        """
        Add a member to an existing cash round
        
        Args:
            cash_round: CashRound instance
            member: SaccoMember instance
            position: Optional position in rotation (defaults to end)
            
        Returns:
            CashRoundMember instance
        """
        if cash_round.status == 'completed':
            raise ValueError("Cannot add members to a completed cash round")
        
        # Check if member already in round
        if CashRoundMember.objects.filter(cash_round=cash_round, member=member, is_active=True).exists():
            raise ValueError("Member is already in this cash round")
        
        # Determine position
        if position is None:
            max_position = CashRoundMember.objects.filter(cash_round=cash_round).count()
            position = max_position
        
        # Create the member entry
        round_member = CashRoundMember.objects.create(
            cash_round=cash_round,
            member=member,
            position_in_rotation=position,
            is_active=True
        )
        
        # Update the schedule's rotation order
        if hasattr(cash_round, 'schedule'):
            rotation_order = cash_round.schedule.rotation_order or []
            if member.id not in rotation_order:
                rotation_order.insert(position, member.id)
                cash_round.schedule.rotation_order = rotation_order
                cash_round.schedule.save()
        
        # Update num_weeks and expected_end_date
        cash_round.num_weeks = CashRoundMember.objects.filter(cash_round=cash_round, is_active=True).count()
        cash_round.expected_end_date = cash_round.start_date + timedelta(weeks=cash_round.num_weeks)
        cash_round.save()
        
        return round_member
    
    @staticmethod
    @transaction.atomic
    def remove_member_from_round(cash_round, member):
        """
        Remove a member from a cash round
        
        Args:
            cash_round: CashRound instance
            member: SaccoMember instance
            
        Returns:
            bool: True if removed successfully
        """
        if cash_round.status == 'completed':
            raise ValueError("Cannot remove members from a completed cash round")
        
        # Mark member as inactive
        round_member = CashRoundMember.objects.filter(
            cash_round=cash_round,
            member=member,
            is_active=True
        ).first()
        
        if not round_member:
            raise ValueError("Member is not in this cash round")
        
        round_member.is_active = False
        round_member.left_at = timezone.now()
        round_member.save()
        
        # Update the schedule's rotation order
        if hasattr(cash_round, 'schedule'):
            rotation_order = cash_round.schedule.rotation_order or []
            if member.id in rotation_order:
                rotation_order.remove(member.id)
                cash_round.schedule.rotation_order = rotation_order
                cash_round.schedule.save()
        
        # Update num_weeks
        cash_round.num_weeks = CashRoundMember.objects.filter(cash_round=cash_round, is_active=True).count()
        cash_round.expected_end_date = cash_round.start_date + timedelta(weeks=cash_round.num_weeks)
        cash_round.save()
        
        return True
    
    @staticmethod
    def get_active_rounds(sacco):
        """
        Get all active cash rounds for a SACCO
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            QuerySet of active CashRound instances
        """
        return CashRound.objects.filter(sacco=sacco, status='active')
    
    @staticmethod
    def get_member_rounds(member):
        """
        Get all cash rounds a member is part of
        
        Args:
            member: SaccoMember instance
            
        Returns:
            QuerySet of CashRound instances
        """
        return CashRound.objects.filter(
            round_members__member=member,
            round_members__is_active=True
        ).distinct()
    
    @staticmethod
    @transaction.atomic
    def start_round_with_first_meeting(cash_round, user=None):
        """
        Start a cash round and create the first meeting automatically
        
        Args:
            cash_round: CashRound instance
            user: User creating the meeting
            
        Returns:
            dict with cash_round and meeting
        """
        from saccos.models import WeeklyMeeting
        from datetime import date, timedelta
        
        if cash_round.status != 'planned':
            raise ValueError(f"Cannot start cash round with status '{cash_round.status}'")
        
        if not hasattr(cash_round, 'schedule') or not cash_round.schedule:
            raise ValueError("Cash round has no schedule")
        
        # Start the round
        cash_round.start_round()
        
        # Activate the schedule
        cash_round.schedule.is_active = True
        cash_round.schedule.save()
        
        # Get the first recipient
        recipient = cash_round.schedule.get_current_recipient()
        if not recipient:
            raise ValueError("No members in rotation")
        
        # Calculate meeting date (use start_date or today if start_date is in the past)
        meeting_date = cash_round.start_date
        if meeting_date < date.today():
            meeting_date = date.today()
        
        # Get year and week number
        year = meeting_date.year
        week_number = 1  # First week of the round
        
        # Create the first meeting
        meeting = WeeklyMeeting.objects.create(
            sacco=cash_round.sacco,
            cash_round=cash_round,
            meeting_date=meeting_date,
            week_number=week_number,
            year=year,
            cash_round_recipient=recipient,
            status='planned'
        )
        
        return {
            'cash_round': cash_round,
            'meeting': meeting
        }
    
    @staticmethod
    @transaction.atomic
    def create_next_meeting(cash_round, user=None):
        """
        Create the next meeting in the cash round based on schedule
        
        Args:
            cash_round: CashRound instance
            user: User creating the meeting
            
        Returns:
            dict with meeting
        """
        from saccos.models import WeeklyMeeting
        from datetime import date, timedelta
        
        if cash_round.status != 'active':
            raise ValueError(f"Cannot create meeting for cash round with status '{cash_round.status}'")
        
        if not hasattr(cash_round, 'schedule') or not cash_round.schedule:
            raise ValueError("Cash round has no schedule")
        
        # Get the last meeting to determine next week
        last_meeting = WeeklyMeeting.objects.filter(
            cash_round=cash_round
        ).order_by('-week_number').first()
        
        if not last_meeting:
            # No previous meeting - need to create the first one
            # Get the first recipient
            recipient = cash_round.schedule.get_current_recipient()
            if not recipient:
                raise ValueError("No members in rotation")
            
            # Calculate meeting date (use start_date or today if start_date is in the past)
            meeting_date = cash_round.start_date
            if meeting_date < date.today():
                meeting_date = date.today()
            
            # Get year and week number
            year = meeting_date.year
            week_number = 1  # First week of the round
            
            # Create the first meeting
            meeting = WeeklyMeeting.objects.create(
                sacco=cash_round.sacco,
                cash_round=cash_round,
                meeting_date=meeting_date,
                week_number=week_number,
                year=year,
                cash_round_recipient=recipient,
                status='planned'
            )
            
            return {
                'meeting': meeting
            }
        
        # Check if last meeting is completed
        if last_meeting.status != 'completed':
            raise ValueError("Previous meeting must be completed before creating next meeting")
        
        # Advance to next member in rotation
        cash_round.schedule.advance_to_next_member()
        
        # Get the next recipient
        recipient = cash_round.schedule.get_current_recipient()
        if not recipient:
            raise ValueError("No recipient found for next meeting")
        
        # Calculate next meeting date (7 days from last meeting)
        next_date = last_meeting.meeting_date + timedelta(days=7)
        
        # Get year and week number
        year = next_date.year
        week_number = last_meeting.week_number + 1
        
        # Create the next meeting
        meeting = WeeklyMeeting.objects.create(
            sacco=cash_round.sacco,
            cash_round=cash_round,
            meeting_date=next_date,
            week_number=week_number,
            year=year,
            cash_round_recipient=recipient,
            status='planned'
        )
        
        return {
            'meeting': meeting
        }
