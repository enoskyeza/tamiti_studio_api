from django.db import models
from django.utils import timezone
from decimal import Decimal
from core.models import BaseModel
from users.models import User
from finance.models import Account


class SaccoOrganization(BaseModel):
    """
    Main tenant model - each SACCO is an organization
    Phase 1: Foundation
    """
    # Basic Information
    name = models.CharField(max_length=255, help_text="SACCO name")
    registration_number = models.CharField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    
    # Contact Information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    # Configuration
    settings = models.JSONField(default=dict, blank=True, help_text="SACCO-specific settings")
    
    # Cash Round Configuration
    cash_round_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=51000,
        help_text="Standard weekly contribution per member"
    )
    meeting_day = models.CharField(
        max_length=20, 
        default='Saturday',
        help_text="Day of the week for meetings"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # SaaS Fields (for future Phase 6)
    subscription_plan = models.CharField(max_length=50, default='basic')
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('cancelled', 'Cancelled')
        ],
        default='trial'
    )
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Admin Users
    admins = models.ManyToManyField(
        User, 
        related_name='administered_saccos',
        help_text="Users who can manage this SACCO"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SACCO Organization'
        verbose_name_plural = 'SACCO Organizations'
    
    def __str__(self):
        return self.name
    
    def is_subscription_active(self):
        """Check if subscription is valid"""
        if self.subscription_status != 'active':
            return False
        if self.subscription_expires_at:
            return timezone.now() < self.subscription_expires_at
        return True
    
    @property
    def member_count(self):
        """Total number of active members"""
        return self.members.filter(status='active').count()
    
    def get_or_create_account(self):
        """Get or create the SACCO's financial account"""
        from saccos.services.sacco_account_service import SaccoAccountService
        return SaccoAccountService.get_or_create_sacco_account(self)


class SaccoAccount(BaseModel):
    """
    Links a SACCO organization to its financial account
    Uses the existing finance.Account infrastructure
    """
    sacco = models.OneToOneField(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='sacco_account'
    )
    account = models.OneToOneField(
        Account,
        on_delete=models.PROTECT,
        related_name='sacco_link',
        help_text="Link to the finance Account model"
    )
    
    # Additional SACCO-specific fields
    bank_name = models.CharField(max_length=100, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    
    class Meta:
        verbose_name = "SACCO Account"
        verbose_name_plural = "SACCO Accounts"
    
    def __str__(self):
        return f"{self.sacco.name} - Account"
    
    @property
    def current_balance(self):
        """Get current balance from linked account"""
        return self.account.balance if self.account else Decimal('0')


class SaccoMember(BaseModel):
    """
    Member of a SACCO - links User to Organization
    Phase 1: Foundation
    """
    # Links
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='sacco_membership'
    )
    sacco = models.ForeignKey(
        SaccoOrganization, 
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Member Information
    member_number = models.CharField(max_length=50, help_text="Unique within SACCO")
    passbook_number = models.CharField(max_length=50, blank=True)
    
    # Personal Details
    national_id = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    
    # Contact
    address = models.TextField(blank=True)
    alternative_phone = models.CharField(max_length=20, blank=True)
    
    # Next of Kin
    next_of_kin_name = models.CharField(max_length=255, blank=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True)
    next_of_kin_relationship = models.CharField(max_length=100, blank=True)
    
    # Membership Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('inactive', 'Inactive'),
            ('resigned', 'Resigned')
        ],
        default='active'
    )
    date_joined = models.DateField(auto_now_add=True)
    date_left = models.DateField(null=True, blank=True)
    
    # Roles in SACCO
    is_secretary = models.BooleanField(default=False)
    is_treasurer = models.BooleanField(default=False)
    is_chairperson = models.BooleanField(default=False)
    role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Member's role (Chairperson, Secretary, Treasurer, Committee Member, etc.)"
    )
    
    # Savings Goal
    savings_goal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Member's personal savings goal"
    )
    savings_goal_deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Target date to reach savings goal"
    )
    
    class Meta:
        ordering = ['member_number']
        unique_together = [['sacco', 'member_number']]
        indexes = [
            models.Index(fields=['sacco', 'status']),
        ]
    
    def __str__(self):
        return f"{self.member_number} - {self.user.get_full_name()}"
    
    def get_passbook(self):
        """Get or create member's passbook"""
        passbook, created = MemberPassbook.objects.get_or_create(
            member=self,
            sacco=self.sacco,
            defaults={'passbook_number': self.passbook_number or self.member_number}
        )
        return passbook


class MemberPassbook(BaseModel):
    """
    A member's passbook - container for all their transactions
    Phase 1: Foundation
    """
    member = models.OneToOneField(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='passbook'
    )
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='passbooks'
    )
    passbook_number = models.CharField(max_length=50, unique=True)
    issued_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['passbook_number']
    
    def __str__(self):
        return f"Passbook {self.passbook_number} - {self.member.user.get_full_name()}"
    
    def get_section_balance(self, section):
        """Get current balance for a specific section"""
        from django.db.models import Sum
        
        credits = self.entries.filter(
            section=section,
            transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        debits = self.entries.filter(
            section=section,
            transaction_type='debit'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return credits - debits
    
    def get_all_balances(self):
        """Get balances for all sections"""
        sections = PassbookSection.objects.filter(sacco=self.sacco, is_active=True)
        balances = {}
        
        for section in sections:
            balances[section.id] = {
                'section_id': section.id,
                'section_name': section.name,
                'section_type': section.section_type,
                'balance': float(self.get_section_balance(section))
            }
        
        return balances


class PassbookSection(BaseModel):
    """
    Configurable sections in a passbook
    Different SACCOs can have different sections
    Phase 2: Passbook System
    """
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='passbook_sections'
    )
    
    # Section Details
    name = models.CharField(max_length=100, help_text="e.g., 'Compulsory Savings'")
    section_type = models.CharField(
        max_length=50,
        choices=[
            ('savings', 'Savings'),
            ('welfare', 'Welfare'),
            ('development', 'Development'),
            ('loan', 'Loan'),
            ('emergency', 'Emergency'),
            ('interest', 'Interest'),
            ('other', 'Other')
        ]
    )
    description = models.TextField(blank=True)
    
    # Configuration
    is_compulsory = models.BooleanField(default=False, help_text="Must contribute weekly")
    weekly_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Fixed weekly amount if compulsory"
    )
    allow_variable_amounts = models.BooleanField(
        default=True,
        help_text="Allow members to contribute different amounts"
    )
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Color for UI
    color = models.CharField(max_length=7, default='#3B82F6', help_text="Hex color code")
    
    class Meta:
        ordering = ['sacco', 'display_order', 'name']
        unique_together = [['sacco', 'name']]
    
    def __str__(self):
        return f"{self.sacco.name} - {self.name}"
    
    @classmethod
    def create_default_sections(cls, sacco):
        """Create default sections for a new SACCO"""
        default_sections = [
            {
                'name': 'Compulsory Savings',
                'section_type': 'savings',
                'is_compulsory': True,
                'weekly_amount': 2000,
                'display_order': 1,
                'color': '#10B981'
            },
            {
                'name': 'Optional Savings',
                'section_type': 'savings',
                'is_compulsory': False,
                'allow_variable_amounts': True,
                'display_order': 2,
                'color': '#059669'
            },
            {
                'name': 'Welfare',
                'section_type': 'welfare',
                'is_compulsory': True,
                'weekly_amount': 5000,
                'display_order': 3,
                'color': '#8B5CF6'
            },
            {
                'name': 'Development',
                'section_type': 'development',
                'is_compulsory': True,
                'weekly_amount': 5000,
                'display_order': 4,
                'color': '#F59E0B'
            },
            {
                'name': 'Loan',
                'section_type': 'loan',
                'is_compulsory': False,
                'display_order': 5,
                'color': '#EF4444'
            },
            {
                'name': 'Emergency',
                'section_type': 'emergency',
                'is_compulsory': False,
                'display_order': 6,
                'color': '#DC2626'
            },
            {
                'name': 'Interest',
                'section_type': 'interest',
                'is_compulsory': False,
                'display_order': 7,
                'color': '#6366F1'
            }
        ]
        
        sections = []
        for section_data in default_sections:
            section = cls.objects.create(sacco=sacco, **section_data)
            sections.append(section)
        
        return sections


class PassbookEntry(BaseModel):
    """
    Individual transaction entry in a passbook section
    Immutable - cannot be deleted, only reversed
    Phase 2: Passbook System
    """
    # Core References
    passbook = models.ForeignKey(
        MemberPassbook,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    section = models.ForeignKey(
        PassbookSection,
        on_delete=models.PROTECT,
        related_name='entries'
    )
    
    # Transaction Details
    transaction_date = models.DateField()
    transaction_type = models.CharField(
        max_length=10,
        choices=[
            ('credit', 'Credit'),  # Money added to section (payment in)
            ('debit', 'Debit')     # Money removed from section (payment out)
        ]
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Running Balance
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Balance of this section after this entry"
    )
    
    # Description & Reference
    description = models.TextField()
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Audit Trail
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_passbook_entries'
    )
    
    # Weekly Meeting Link (Phase 3)
    meeting = models.ForeignKey(
        'WeeklyMeeting',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='passbook_entries',
        help_text="Link to the weekly meeting where this transaction occurred"
    )
    week_number = models.PositiveIntegerField(null=True, blank=True)
    
    # Reversal Support
    is_reversal = models.BooleanField(default=False)
    reverses_entry = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversed_by'
    )
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['passbook', 'section']),
            models.Index(fields=['transaction_date']),
        ]
        verbose_name_plural = 'Passbook Entries'
    
    def __str__(self):
        return f"{self.passbook.member.user.get_full_name()} - {self.section.name}: {self.amount}"
    
    def save(self, *args, **kwargs):
        """
        Override save to auto-recalculate meeting totals when entries are added
        to completed meetings (handles post-finalization extras)
        """
        # Calculate balance_after if not set
        if not self.balance_after:
            previous_balance = self.get_previous_balance()
            if self.transaction_type == 'credit':
                self.balance_after = previous_balance + self.amount
            else:  # debit
                self.balance_after = previous_balance - self.amount
        
        super().save(*args, **kwargs)
        
        # Update meeting totals if this entry is linked to a meeting
        if self.meeting:
            self.meeting.calculate_totals()
    
    def delete(self, *args, **kwargs):
        # Store meeting reference before deletion
        meeting = self.meeting
        super().delete(*args, **kwargs)
        
        # Update meeting totals after deletion
        if meeting:
            meeting.calculate_totals()
    
    def get_previous_balance(self):
        """Get the balance before this entry"""
        last_entry = PassbookEntry.objects.filter(
            passbook=self.passbook,
            section=self.section,
            created_at__lt=self.created_at if self.created_at else timezone.now()
        ).order_by('-created_at').first()
        
        return last_entry.balance_after if last_entry else Decimal('0')


class DeductionRule(BaseModel):
    """
    Configurable deduction rules for cash round recipients
    Phase 2: Passbook System (Updated to link to CashRound)
    """
    # NEW: Link to CashRound instead of SACCO
    cash_round = models.ForeignKey(
        'CashRound',  # String reference since CashRound is defined later
        on_delete=models.CASCADE,
        related_name='deduction_rules',
        null=True,  # Nullable during migration
        blank=True
    )
    
    # DEPRECATED: Will be removed after migration
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='deduction_rules',
        null=True,  # Nullable during migration
        blank=True
    )
    
    section = models.ForeignKey(
        PassbookSection,
        on_delete=models.CASCADE,
        related_name='deduction_rules'
    )
    
    # Deduction Amount
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Applicability
    applies_to = models.CharField(
        max_length=20,
        choices=[
            ('recipient', 'Cash Round Recipient'),
            ('all_members', 'All Members'),
            ('specific', 'Specific Members')
        ],
        default='recipient'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    
    # Description
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sacco', 'section']
    
    def __str__(self):
        return f"{self.sacco.name} - {self.section.name} - {self.amount}"
    
    def is_effective(self, date=None):
        """Check if rule is effective on a given date"""
        if not self.is_active:
            return False
        
        check_date = date or timezone.now().date()
        
        if check_date < self.effective_from:
            return False
        
        if self.effective_until and check_date > self.effective_until:
            return False
        
        return True


# ============================================================================
# PHASE 3: WEEKLY MEETINGS & CASH ROUNDS
# ============================================================================


class CashRound(BaseModel):
    """
    A cash round cycle with specific members and schedule.
    Multiple rounds can run concurrently.
    Phase 3: Weekly Meetings & Cash Rounds (Restructured)
    """
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='cash_rounds'
    )
    
    # Identity
    name = models.CharField(max_length=200, help_text="e.g., Round 1 - January 2025")
    round_number = models.PositiveIntegerField(help_text="Auto-increment per SACCO")
    
    # Schedule
    start_date = models.DateField()
    expected_end_date = models.DateField(help_text="Auto-calc: start + (num_members * weeks)")
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Configuration
    weekly_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="How much each member pays per week"
    )
    num_weeks = models.PositiveIntegerField(help_text="Usually = number of members")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planned'),      # Created but not started
            ('active', 'Active'),        # Currently running
            ('completed', 'Completed'),  # Finished
            ('cancelled', 'Cancelled')
        ],
        default='planned'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_cash_rounds'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        unique_together = [['sacco', 'round_number']]
        indexes = [
            models.Index(fields=['sacco', 'status']),
        ]
    
    def __str__(self):
        return f"{self.sacco.name} - {self.name}"
    
    @property
    def is_active(self):
        """Check if round is currently active"""
        return self.status == 'active'
    
    def start_round(self):
        """Activate the cash round"""
        if self.status == 'planned':
            self.status = 'active'
            self.started_at = timezone.now()
            self.save()
    
    def complete_round(self):
        """Mark round as completed"""
        if self.status == 'active':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.actual_end_date = timezone.now().date()
            self.save()


class CashRoundMember(BaseModel):
    """
    Junction table: which SACCO members are in which cash round.
    Phase 3: Weekly Meetings & Cash Rounds (Restructured)
    """
    cash_round = models.ForeignKey(
        CashRound,
        on_delete=models.CASCADE,
        related_name='round_members'
    )
    member = models.ForeignKey(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='cash_rounds'
    )
    
    # Position in rotation
    position_in_rotation = models.PositiveIntegerField()
    
    # Status
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['cash_round', 'member']]
        ordering = ['position_in_rotation']
        indexes = [
            models.Index(fields=['cash_round', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.member.user.get_full_name()} in {self.cash_round.name}"


class CashRoundSchedule(BaseModel):
    """
    Schedule for cash round rotation
    Tracks which member receives the cash round each week
    Phase 3: Weekly Meetings (Restructured to link to CashRound)
    """
    # NEW: Link to CashRound
    cash_round = models.OneToOneField(
        CashRound,
        on_delete=models.CASCADE,
        related_name='schedule',
        null=True,  # Nullable during migration
        blank=True
    )
    
    # DEPRECATED: Will be removed after migration - keep for backward compatibility
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='cash_round_schedules',
        null=True,  # Nullable during migration
        blank=True
    )
    
    # Schedule Details - DEPRECATED (moved to CashRound)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Rotation
    rotation_order = models.JSONField(
        default=list,
        help_text="List of member IDs in rotation order"
    )
    current_position = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.sacco.name} - Cash Round Schedule (Started {self.start_date})"
    
    def get_current_recipient(self):
        """Get the member who should receive cash round this week"""
        if not self.rotation_order:
            return None
        
        member_id = self.rotation_order[self.current_position]
        return SaccoMember.objects.filter(id=member_id).first()
    
    def advance_to_next_member(self):
        """Move to next member in rotation"""
        if not self.rotation_order:
            return
        
        self.current_position = (self.current_position + 1) % len(self.rotation_order)
        self.save()
    
    def get_next_recipient(self):
        """Preview who will receive next"""
        if not self.rotation_order:
            return None
        
        next_position = (self.current_position + 1) % len(self.rotation_order)
        member_id = self.rotation_order[next_position]
        return SaccoMember.objects.filter(id=member_id).first()


class WeeklyMeeting(BaseModel):
    """
    Weekly SACCO meeting record
    Phase 3: Weekly Meetings (Restructured to link to CashRound)
    """
    # NEW: Link to CashRound
    cash_round = models.ForeignKey(
        CashRound,
        on_delete=models.CASCADE,
        related_name='meetings',
        null=True,  # Nullable during migration
        blank=True
    )
    
    # Keep for queries - not deprecated
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='weekly_meetings'
    )
    
    # Meeting Details
    meeting_date = models.DateField()
    week_number = models.PositiveIntegerField(help_text="Week number in cash round cycle")
    year = models.PositiveIntegerField()
    
    # Cash Round
    cash_round_recipient = models.ForeignKey(
        SaccoMember,
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_cash_rounds'
    )
    
    # Totals
    total_collected = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total amount collected from all members"
    )
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total deductions from recipient"
    )
    amount_to_recipient = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount given to cash round recipient"
    )
    amount_to_bank = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount sent to bank (deductions + optional savings)"
    )
    
    # Attendance
    members_present = models.PositiveIntegerField(default=0)
    members_absent = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planned'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='planned'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Audit
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_meetings'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-meeting_date']
        unique_together = [['sacco', 'meeting_date']]
        indexes = [
            models.Index(fields=['sacco', 'year', 'week_number']),
        ]
    
    def __str__(self):
        return f"{self.sacco.name} - Week {self.week_number} ({self.meeting_date})"
    
    def calculate_totals(self):
        """
        Recalculate all meeting totals
        
        CRITICAL: After finalization, passbook entries are the source of truth
        Before finalization, we calculate from contributions
        """
        from decimal import Decimal
        
        # Basic collection stats
        self.members_present = self.contributions.filter(was_present=True).count()
        self.members_absent = self.contributions.filter(was_present=False).count()
        
        # Total collected from present members
        present_contributions = self.contributions.filter(was_present=True)
        self.total_collected = sum(
            (c.amount_contributed or Decimal('0')) for c in present_contributions
        )
        
        if self.status == 'completed':
            # POST-FINALIZATION: Use passbook entries as single source of truth
            # This includes deductions + optional savings + any extras added after finalization
            passbook_entries = PassbookEntry.objects.filter(
                meeting=self,
                transaction_type='credit'  # All savings are credits
            )
            
            # Sum all actual entries (deductions + extras + optional savings)
            self.amount_to_bank = sum(entry.amount for entry in passbook_entries)
            
            # Deductions are now just informational (already in passbook)
            # Keep the value for historical reference but don't use in calculations
            
        else:
            # PRE-FINALIZATION: Calculate from contributions (planned amounts)
            optional_savings = sum(
                (c.optional_savings or Decimal('0')) for c in present_contributions
            )
            
            # Calculate deductions from recipient (if exists)
            total_deductions = Decimal('0')
            if self.cash_round_recipient:
                recipient_contribution = self.contributions.filter(
                    member=self.cash_round_recipient,
                    is_recipient=True
                ).first()
                
                if recipient_contribution:
                    total_deductions = recipient_contribution.total_deductions or Decimal('0')
            
            self.total_deductions = total_deductions
            
            # Amount to bank = deductions from recipient + optional savings from all
            self.amount_to_bank = total_deductions + optional_savings
        
        # Amount to recipient = total collected - deductions
        self.amount_to_recipient = self.total_collected - self.total_deductions
        
        self.save()
    
    def get_current_recipient(self):
        """Get the member who should receive cash round this week"""
        if not self.cash_round_recipient:
            return None
        
        return self.cash_round_recipient
    
    def get_next_recipient(self):
        """Preview who will receive next"""
        if not self.cash_round_recipient:
            return None
        
        next_recipient = self.contributions.filter(
            member=self.cash_round_recipient,
            is_recipient=True
        ).first()
        
        if next_recipient:
            return next_recipient.member
    
    def get_previous_recipient(self):
        """Get the previous recipient"""
        if not self.cash_round_recipient:
            return None
        
        previous_recipient = self.contributions.filter(
            member=self.cash_round_recipient,
            is_recipient=True
        ).first()
        
        if previous_recipient:
            return previous_recipient.member


class WeeklyContribution(BaseModel):
    """
    Individual member's contribution for a weekly meeting
    Phase 3: Weekly Meetings
    """
    meeting = models.ForeignKey(
        WeeklyMeeting,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    member = models.ForeignKey(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='weekly_contributions'
    )
    
    # Contribution Details
    was_present = models.BooleanField(default=True)
    amount_contributed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total amount this member contributed"
    )
    
    # Optional Savings (from all members)
    optional_savings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Optional savings amount"
    )
    
    # Deductions (ONLY for recipient)
    is_recipient = models.BooleanField(default=False)
    compulsory_savings_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    welfare_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    development_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    other_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Sum of all deductions"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['meeting', 'member']
        unique_together = [['meeting', 'member']]
    
    def __str__(self):
        return f"{self.member.member_number} - Week {self.meeting.week_number}"
    
    def calculate_total_deductions(self):
        """Calculate total deductions"""
        self.total_deductions = (
            self.compulsory_savings_deduction +
            self.welfare_deduction +
            self.development_deduction +
            self.other_deductions
        )
        return self.total_deductions
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update meeting totals after saving contribution
        if self.meeting:
            self.meeting.calculate_totals()
    
    def delete(self, *args, **kwargs):
        meeting = self.meeting
        super().delete(*args, **kwargs)
        # Update meeting totals after deleting contribution
        if meeting:
            meeting.calculate_totals()


# ============================================================================
# PHASE 4: LOAN MANAGEMENT
# ============================================================================


class SaccoLoan(BaseModel):
    """
    Loan issued to a SACCO member
    Phase 4: Loan Management
    """
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='loans'
    )
    member = models.ForeignKey(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='loans'
    )
    
    # Loan Details
    loan_number = models.CharField(max_length=50, unique=True)
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Original loan amount"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Interest rate percentage"
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total interest to be paid"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Principal + Interest"
    )
    
    # Loan Period
    application_date = models.DateField()
    approval_date = models.DateField(null=True, blank=True)
    disbursement_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    duration_months = models.PositiveIntegerField(default=12)
    
    # Payment Tracking
    amount_paid_principal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    amount_paid_interest = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    balance_principal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    balance_interest = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('disbursed', 'Disbursed'),
            ('active', 'Active'),
            ('paid', 'Fully Paid'),
            ('defaulted', 'Defaulted'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    
    # Purpose & Notes
    purpose = models.TextField(help_text="Reason for loan")
    notes = models.TextField(blank=True)
    
    # Approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_loans'
    )
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['sacco', 'status']),
            models.Index(fields=['member', 'status']),
        ]
    
    def __str__(self):
        return f"{self.loan_number} - {self.member.member_number} - {self.principal_amount}"
    
    def calculate_interest(self):
        """Calculate total interest amount"""
        self.interest_amount = (self.principal_amount * self.interest_rate) / 100
        self.total_amount = self.principal_amount + self.interest_amount
        self.balance_principal = self.principal_amount
        self.balance_interest = self.interest_amount
        return self.interest_amount
    
    def update_balances(self):
        """Recalculate balances from payments"""
        payments = self.payments.all()
        
        self.amount_paid_principal = sum(p.principal_amount for p in payments)
        self.amount_paid_interest = sum(p.interest_amount for p in payments)
        
        self.balance_principal = self.principal_amount - self.amount_paid_principal
        self.balance_interest = self.interest_amount - self.amount_paid_interest
        
        # Update status if fully paid
        if self.balance_principal <= 0 and self.balance_interest <= 0:
            self.status = 'paid'
        
        self.save()
    
    @property
    def total_balance(self):
        """Total remaining balance"""
        return self.balance_principal + self.balance_interest
    
    @property
    def is_overdue(self):
        """Check if loan is overdue"""
        if not self.due_date or self.status in ['paid', 'rejected']:
            return False
        return timezone.now().date() > self.due_date


class LoanPayment(BaseModel):
    """
    Payment made towards a loan
    Phase 4: Loan Management
    """
    loan = models.ForeignKey(
        SaccoLoan,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Payment Details
    payment_date = models.DateField()
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total payment amount"
    )
    
    # Split between principal and interest
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount applied to principal"
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount applied to interest"
    )
    
    # Reference
    payment_method = models.CharField(max_length=50, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Audit
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_loan_payments'
    )
    
    # Link to passbook entry
    passbook_entry = models.ForeignKey(
        PassbookEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_payments'
    )
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.loan.loan_number} - Payment {self.total_amount} on {self.payment_date}"
    
    def save(self, *args, **kwargs):
        # Ensure total matches split
        if self.principal_amount or self.interest_amount:
            self.total_amount = self.principal_amount + self.interest_amount
        
        super().save(*args, **kwargs)
        
        # Update loan balances
        self.loan.update_balances()


class LoanGuarantor(BaseModel):
    """
    Guarantor for a loan
    Phase 4: Loan Management
    """
    loan = models.ForeignKey(
        SaccoLoan,
        on_delete=models.CASCADE,
        related_name='guarantors'
    )
    guarantor = models.ForeignKey(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='guaranteed_loans'
    )
    
    # Guarantee Details
    guarantee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount guaranteed"
    )
    guarantee_date = models.DateField(auto_now_add=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = [['loan', 'guarantor']]
    
    def __str__(self):
        return f"{self.guarantor.member_number} guarantees {self.loan.loan_number}"


class SaccoEmergencySupport(BaseModel):
    """
    Emergency support given to a member
    Phase 4: Loan Management
    """
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='emergency_supports'
    )
    member = models.ForeignKey(
        SaccoMember,
        on_delete=models.CASCADE,
        related_name='emergency_supports'
    )
    
    # Support Details
    support_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(help_text="Emergency reason")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('disbursed', 'Disbursed'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    
    # Approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_emergency_supports'
    )
    approval_date = models.DateField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Link to passbook entry
    passbook_entry = models.ForeignKey(
        PassbookEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emergency_supports'
    )
    
    class Meta:
        ordering = ['-support_date']
    
    def __str__(self):
        return f"{self.member.member_number} - Emergency {self.amount} on {self.support_date}"
# ============================================================================
# PHASE 6: SAAS FEATURES
# ============================================================================


class SubscriptionPlan(BaseModel):
    """
    Subscription plans for SaaS offering
    Phase 6: SaaS Features
    """
    # Plan Details
    name = models.CharField(max_length=100)  # Basic, Pro, Enterprise
    description = models.TextField()
    
    # Pricing
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Annual subscription price (usually discounted)"
    )
    currency = models.CharField(max_length=3, default='UGX')
    
    # Limits
    max_members = models.PositiveIntegerField(
        help_text="Maximum number of members allowed"
    )
    max_weekly_meetings = models.PositiveIntegerField(
        default=52,
        help_text="Maximum meetings per year"
    )
    max_storage_mb = models.PositiveIntegerField(
        default=1000,
        help_text="Storage limit in MB"
    )
    
    # Features (JSON field for flexibility)
    features = models.JSONField(
        default=dict,
        help_text="Feature flags: {'advanced_reports': true, 'api_access': false, ...}"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Show this plan on public pricing page"
    )
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'monthly_price']
    
    def __str__(self):
        return f"{self.name} - {self.monthly_price} {self.currency}/month"
    
    @property
    def yearly_discount_percentage(self):
        """Calculate discount for yearly vs monthly"""
        monthly_equivalent = self.monthly_price * 12
        if monthly_equivalent > 0:
            return ((monthly_equivalent - self.yearly_price) / monthly_equivalent) * 100
        return 0


class SaccoSubscription(BaseModel):
    """
    Subscription instance for a SACCO
    Phase 6: SaaS Features
    """
    sacco = models.OneToOneField(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    # Billing Cycle
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly')
        ],
        default='monthly'
    )
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField()
    trial_end_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('suspended', 'Suspended'),
            ('cancelled', 'Cancelled')
        ],
        default='trial'
    )
    
    # Auto Renewal
    auto_renew = models.BooleanField(default=True)
    cancel_at_period_end = models.BooleanField(default=False)
    
    # Payment
    next_billing_date = models.DateField()
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Billing Contact
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sacco.name} - {self.plan.name}"
    
    def is_active(self):
        """Check if subscription is currently active"""
        if self.status not in ['trial', 'active']:
            return False
        
        today = timezone.now().date()
        
        # Check trial
        if self.status == 'trial' and self.trial_end_date:
            return today <= self.trial_end_date
        
        # Check subscription period
        return today <= self.end_date
    
    def days_until_expiry(self):
        """Get days remaining on subscription"""
        today = timezone.now().date()
        expiry = self.trial_end_date if self.status == 'trial' else self.end_date
        
        if expiry:
            delta = expiry - today
            return max(0, delta.days)
        return 0
    
    def renew(self):
        """Renew subscription for another billing cycle"""
        from dateutil.relativedelta import relativedelta
        
        if self.billing_cycle == 'monthly':
            self.end_date = self.end_date + relativedelta(months=1)
            self.next_billing_date = self.end_date
        else:  # yearly
            self.end_date = self.end_date + relativedelta(years=1)
            self.next_billing_date = self.end_date
        
        self.status = 'active'
        self.last_payment_date = timezone.now().date()
        self.save()


class SubscriptionInvoice(BaseModel):
    """
    Invoice for subscription payments
    Phase 6: SaaS Features
    """
    subscription = models.ForeignKey(
        SaccoSubscription,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    # Invoice Details
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    
    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    
    # Payment
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    paid_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    class Meta:
        ordering = ['-invoice_date']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.subscription.sacco.name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            count = SubscriptionInvoice.objects.count()
            self.invoice_number = f"INV-{count+1:06d}"
        super().save(*args, **kwargs)


class UsageMetrics(BaseModel):
    """
    Track usage metrics for subscription enforcement
    Phase 6: SaaS Features
    """
    sacco = models.ForeignKey(
        SaccoOrganization,
        on_delete=models.CASCADE,
        related_name='usage_metrics'
    )
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Usage Counts
    active_members_count = models.PositiveIntegerField(default=0)
    meetings_held = models.PositiveIntegerField(default=0)
    loans_created = models.PositiveIntegerField(default=0)
    storage_used_mb = models.PositiveIntegerField(default=0)
    api_calls = models.PositiveIntegerField(default=0)
    
    # Financial Metrics
    total_contributions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_loans_disbursed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    class Meta:
        unique_together = [['sacco', 'period_start']]
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.sacco.name} - {self.period_start} to {self.period_end}"
