from rest_framework import serializers
from .models import (
    SaccoOrganization, SaccoMember, MemberPassbook,
    PassbookSection, PassbookEntry, DeductionRule,
    CashRound, CashRoundMember, CashRoundSchedule,
    WeeklyMeeting, WeeklyContribution,
    SaccoLoan, LoanPayment, LoanGuarantor, SaccoEmergencySupport,
    SubscriptionPlan, SaccoSubscription, SubscriptionInvoice, UsageMetrics,
    SaccoAccount
)
from users.models import User


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'avatar']
        read_only_fields = fields


class SaccoOrganizationSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Organization"""
    member_count = serializers.ReadOnlyField()
    is_subscription_active = serializers.ReadOnlyField()
    admins = UserBasicSerializer(many=True, read_only=True)
    admin_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = SaccoOrganization
        fields = [
            'id', 'uuid', 'name', 'registration_number', 'description',
            'email', 'phone', 'address', 'settings',
            'cash_round_amount', 'meeting_day',
            'is_active', 'subscription_plan', 'subscription_status',
            'subscription_expires_at', 'member_count',
            'is_subscription_active', 'admins', 'admin_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'member_count', 'is_subscription_active', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        admin_ids = validated_data.pop('admin_ids', [])
        sacco = SaccoOrganization.objects.create(**validated_data)
        
        if admin_ids:
            admins = User.objects.filter(id__in=admin_ids)
            sacco.admins.set(admins)
        
        return sacco
    
    def update(self, instance, validated_data):
        admin_ids = validated_data.pop('admin_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if admin_ids is not None:
            admins = User.objects.filter(id__in=admin_ids)
            instance.admins.set(admins)
        
        return instance


class SaccoMemberSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Member"""
    user = UserBasicSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    
    class Meta:
        model = SaccoMember
        fields = [
            'id', 'uuid', 'user', 'user_id', 'sacco', 'sacco_name',
            'member_number', 'passbook_number',
            'national_id', 'date_of_birth', 'occupation',
            'address', 'alternative_phone',
            'next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship',
            'status', 'date_joined', 'date_left',
            'is_secretary', 'is_treasurer', 'is_chairperson', 'role',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'sacco_name', 'date_joined', 'created_at', 'updated_at']
    
    def validate_user_id(self, value):
        """Ensure user exists and doesn't already have SACCO membership"""
        try:
            user = User.objects.get(id=value)
            if hasattr(user, 'sacco_membership'):
                raise serializers.ValidationError("This user is already a member of another SACCO")
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value


class SaccoMemberListSerializer(serializers.ModelSerializer):
    """Flattened serializer for SACCO Member list view - matches frontend expectations"""
    # Flatten user fields to top level
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    
    # Calculate totals (placeholder for now - should come from passbook)
    total_savings = serializers.SerializerMethodField()
    total_shares = serializers.SerializerMethodField()
    
    class Meta:
        model = SaccoMember
        fields = [
            'id', 'member_number', 'first_name', 'last_name', 
            'email', 'phone', 'status', 'date_joined',
            'total_savings', 'total_shares', 'address', 
            'profile_picture', 'savings_goal', 'savings_goal_deadline',
            'role', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'member_number', 'first_name', 'last_name',
                           'email', 'phone', 'total_savings', 'total_shares',
                           'profile_picture', 'created_at', 'updated_at']
    
    def get_profile_picture(self, obj):
        """Get user avatar URL"""
        if obj.user and obj.user.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user.avatar.url)
            return obj.user.avatar.url
        return None
    
    def get_total_savings(self, obj):
        """Calculate total savings from passbook sections with type 'savings'"""
        from decimal import Decimal
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            passbook = obj.get_passbook()
            # Get all balances - now returns {section_id: {section_type, balance, ...}}
            all_balances = passbook.get_all_balances()
            
            total = Decimal('0')
            for section_id, balance_data in all_balances.items():
                section_type = balance_data.get('section_type')
                balance = balance_data.get('balance', 0)
                
                # Check if this section is a savings type
                if section_type == 'savings':
                    total += Decimal(str(balance))
            
            return float(total)
        except Exception as e:
            # Log error for debugging
            logger.error(f"Error calculating total savings for member {obj.id}: {str(e)}", exc_info=True)
            return 0
    
    def get_total_shares(self, obj):
        """Calculate total shares from passbook"""
        # TODO: Calculate from passbook entries
        return 0


class MemberPassbookSerializer(serializers.ModelSerializer):
    """Serializer for Member Passbook"""
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    member_number = serializers.CharField(source='member.member_number', read_only=True)
    all_balances = serializers.SerializerMethodField()
    
    class Meta:
        model = MemberPassbook
        fields = [
            'id', 'uuid', 'member', 'member_name', 'member_number',
            'sacco', 'passbook_number', 'issued_date', 'is_active',
            'all_balances', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'member_name', 'member_number', 'issued_date', 'all_balances', 'created_at', 'updated_at']
    
    def get_all_balances(self, obj):
        """Get all section balances"""
        return obj.get_all_balances()


class PassbookSectionSerializer(serializers.ModelSerializer):
    """Serializer for Passbook Section"""
    
    class Meta:
        model = PassbookSection
        fields = [
            'id', 'uuid', 'sacco', 'name', 'section_type', 'description',
            'is_compulsory', 'weekly_amount', 'allow_variable_amounts',
            'display_order', 'is_active', 'color',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class PassbookEntrySerializer(serializers.ModelSerializer):
    """Serializer for Passbook Entry"""
    section_name = serializers.CharField(source='section.name', read_only=True)
    section_type = serializers.CharField(source='section.section_type', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    member_number = serializers.CharField(source='passbook.member.member_number', read_only=True)
    member_name = serializers.CharField(source='passbook.member.user.get_full_name', read_only=True)
    
    class Meta:
        model = PassbookEntry
        fields = [
            'id', 'uuid', 'passbook', 'section', 'section_name', 'section_type',
            'transaction_date', 'transaction_type', 'amount', 'balance_after',
            'description', 'reference_number', 'meeting', 'week_number',
            'recorded_by', 'recorded_by_name', 'member_number', 'member_name',
            'is_reversal', 'reverses_entry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'balance_after', 'section_name', 'section_type',
            'recorded_by_name', 'member_number', 'member_name', 'created_at', 'updated_at'
        ]


class DeductionRuleSerializer(serializers.ModelSerializer):
    """Serializer for Deduction Rule (Updated for CashRound)"""
    section_name = serializers.CharField(source='section.name', read_only=True)
    cash_round_name = serializers.CharField(source='cash_round.name', read_only=True, allow_null=True)
    is_effective_now = serializers.SerializerMethodField()
    
    class Meta:
        model = DeductionRule
        fields = [
            'id', 'uuid', 'cash_round', 'cash_round_name', 'sacco', 
            'section', 'section_name', 'amount', 'applies_to', 'is_active',
            'effective_from', 'effective_until', 'description',
            'is_effective_now', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'cash_round_name', 'section_name', 'is_effective_now', 'created_at', 'updated_at']
        extra_kwargs = {
            'amount': {'required': False}  # Amount is optional, will be set from section
        }
    
    def get_is_effective_now(self, obj):
        """Check if rule is currently effective"""
        return obj.is_effective()


class PassbookStatementSerializer(serializers.Serializer):
    """Serializer for passbook statement generation"""
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    section_id = serializers.IntegerField(required=False)
    
    def validate_start_date(self, value):
        """Ensure start_date is not in the future"""
        from django.utils import timezone
        if value > timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the future")
        return value
    
    def validate(self, data):
        """Ensure start_date is before end_date"""
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("Start date must be before end date")
        return data


# ============================================================================
# PHASE 3: WEEKLY MEETINGS SERIALIZERS
# ============================================================================


class CashRoundMemberSerializer(serializers.ModelSerializer):
    """Serializer for Cash Round Member"""
    member_number = serializers.CharField(source='member.member_number', read_only=True)
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    
    class Meta:
        model = CashRoundMember
        fields = [
            'id', 'uuid', 'cash_round', 'member', 'member_number', 'member_name',
            'position_in_rotation', 'is_active', 'joined_at', 'left_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'member_number', 'member_name', 'joined_at', 'created_at', 'updated_at']


class CashRoundSerializer(serializers.ModelSerializer):
    """Serializer for Cash Round"""
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)
    member_count = serializers.SerializerMethodField()
    members = CashRoundMemberSerializer(source='round_members', many=True, read_only=True)
    
    class Meta:
        model = CashRound
        fields = [
            'id', 'uuid', 'sacco', 'sacco_name', 'name', 'round_number',
            'start_date', 'expected_end_date', 'actual_end_date',
            'weekly_amount', 'num_weeks', 'status',
            'created_by', 'created_by_name', 'started_at', 'completed_at',
            'notes', 'member_count', 'members',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'sacco_name', 'round_number', 'created_by_name',
            'started_at', 'completed_at', 'member_count', 'members',
            'created_at', 'updated_at'
        ]
    
    def get_member_count(self, obj):
        """Get number of active members in this cash round"""
        return obj.round_members.filter(is_active=True).count()


class CashRoundListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Cash Round listing"""
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CashRound
        fields = [
            'id', 'uuid', 'sacco', 'sacco_name', 'name', 'round_number',
            'start_date', 'expected_end_date', 'actual_end_date',
            'weekly_amount', 'num_weeks', 'status', 'member_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'sacco_name', 'round_number', 'member_count', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        """Get number of active members in this cash round"""
        return obj.round_members.filter(is_active=True).count()


class CashRoundScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Cash Round Schedule"""
    current_recipient = serializers.SerializerMethodField()
    next_recipient = serializers.SerializerMethodField()
    
    class Meta:
        model = CashRoundSchedule
        fields = [
            'id', 'uuid', 'cash_round', 'sacco', 'start_date', 'end_date', 'is_active',
            'rotation_order', 'current_position', 'current_recipient',
            'next_recipient', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'current_recipient', 'next_recipient', 'created_at', 'updated_at']
    
    def get_current_recipient(self, obj):
        """Get current recipient details"""
        member = obj.get_current_recipient()
        if member:
            return {
                'id': member.id,
                'member_number': member.member_number,
                'name': member.user.get_full_name()
            }
        return None
    
    def get_next_recipient(self, obj):
        """Get next recipient details"""
        member = obj.get_next_recipient()
        if member:
            return {
                'id': member.id,
                'member_number': member.member_number,
                'name': member.user.get_full_name()
            }
        return None


class WeeklyContributionSerializer(serializers.ModelSerializer):
    """Serializer for Weekly Contribution"""
    member_number = serializers.CharField(source='member.member_number', read_only=True)
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    
    class Meta:
        model = WeeklyContribution
        fields = [
            'id', 'uuid', 'meeting', 'member', 'member_number', 'member_name',
            'was_present', 'amount_contributed', 'optional_savings',
            'is_recipient', 'compulsory_savings_deduction', 'welfare_deduction',
            'development_deduction', 'other_deductions', 'total_deductions',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'member_number', 'member_name', 'created_at', 'updated_at']


class WeeklyMeetingSerializer(serializers.ModelSerializer):
    """Serializer for Weekly Meeting"""
    recipient_name = serializers.CharField(
        source='cash_round_recipient.user.get_full_name',
        read_only=True
    )
    recipient_number = serializers.CharField(
        source='cash_round_recipient.member_number',
        read_only=True
    )
    recorded_by_name = serializers.CharField(
        source='recorded_by.get_full_name',
        read_only=True
    )
    contributions = WeeklyContributionSerializer(many=True, read_only=True)
    
    # Computed attendance fields
    members_present = serializers.SerializerMethodField()
    members_absent = serializers.SerializerMethodField()
    
    def get_members_present(self, obj):
        """Count members who contributed (were present)"""
        return obj.contributions.filter(was_present=True).count()
    
    def get_members_absent(self, obj):
        """Count members who were absent"""
        # Get total active members in SACCO
        total_members = obj.sacco.members.filter(status='active').count()
        members_present = self.get_members_present(obj)
        return total_members - members_present
    
    class Meta:
        model = WeeklyMeeting
        fields = [
            'id', 'uuid', 'sacco', 'meeting_date', 'week_number', 'year',
            'cash_round_recipient', 'recipient_name', 'recipient_number',
            'total_collected', 'total_deductions', 'amount_to_recipient',
            'amount_to_bank', 'members_present', 'members_absent',
            'status', 'notes', 'recorded_by', 'recorded_by_name',
            'completed_at', 'contributions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'recipient_name', 'recipient_number',
            'total_collected', 'total_deductions', 'amount_to_recipient',
            'amount_to_bank', 'members_present', 'members_absent',
            'recorded_by_name', 'completed_at', 'contributions',
            'created_at', 'updated_at'
        ]


# ============================================================================
# PHASE 4: LOAN MANAGEMENT SERIALIZERS
# ============================================================================


class LoanGuarantorSerializer(serializers.ModelSerializer):
    """Serializer for Loan Guarantor"""
    guarantor_number = serializers.CharField(source='guarantor.member_number', read_only=True)
    guarantor_name = serializers.CharField(source='guarantor.user.get_full_name', read_only=True)
    
    class Meta:
        model = LoanGuarantor
        fields = [
            'id', 'uuid', 'loan', 'guarantor', 'guarantor_number',
            'guarantor_name', 'guarantee_amount', 'guarantee_date',
            'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'guarantor_number', 'guarantor_name',
            'guarantee_date', 'created_at', 'updated_at'
        ]


class LoanPaymentSerializer(serializers.ModelSerializer):
    """Serializer for Loan Payment"""
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = LoanPayment
        fields = [
            'id', 'uuid', 'loan', 'payment_date', 'total_amount',
            'principal_amount', 'interest_amount', 'payment_method',
            'reference_number', 'notes', 'recorded_by', 'recorded_by_name',
            'passbook_entry', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'recorded_by_name', 'passbook_entry',
            'created_at', 'updated_at'
        ]


class SaccoLoanSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Loan"""
    member_number = serializers.CharField(source='member.member_number', read_only=True)
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    total_balance = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    guarantors = LoanGuarantorSerializer(many=True, read_only=True)
    payments = LoanPaymentSerializer(many=True, read_only=True)
    
    class Meta:
        model = SaccoLoan
        fields = [
            'id', 'uuid', 'sacco', 'member', 'member_number', 'member_name',
            'loan_number', 'principal_amount', 'interest_rate', 'interest_amount',
            'total_amount', 'application_date', 'approval_date', 'disbursement_date',
            'due_date', 'duration_months', 'amount_paid_principal',
            'amount_paid_interest', 'balance_principal', 'balance_interest',
            'total_balance', 'status', 'purpose', 'notes', 'approved_by',
            'approved_by_name', 'rejection_reason', 'is_overdue',
            'guarantors', 'payments', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'loan_number', 'member_number', 'member_name',
            'interest_amount', 'total_amount', 'amount_paid_principal',
            'amount_paid_interest', 'balance_principal', 'balance_interest',
            'total_balance', 'approved_by_name', 'is_overdue',
            'guarantors', 'payments', 'created_at', 'updated_at'
        ]


class SaccoEmergencySupportSerializer(serializers.ModelSerializer):
    """Serializer for Emergency Support"""
    member_number = serializers.CharField(source='member.member_number', read_only=True)
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = SaccoEmergencySupport
        fields = [
            'id', 'uuid', 'sacco', 'member', 'member_number', 'member_name',
            'support_date', 'amount', 'reason', 'status', 'approved_by',
            'approved_by_name', 'approval_date', 'notes', 'passbook_entry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'member_number', 'member_name', 'approved_by_name',
            'passbook_entry', 'created_at', 'updated_at'
        ]


# ============================================================================
# PHASE 6: SAAS FEATURES SERIALIZERS
# ============================================================================


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for Subscription Plan"""
    yearly_discount_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'uuid', 'name', 'description', 'monthly_price', 'yearly_price',
            'currency', 'yearly_discount_percentage', 'max_members',
            'max_weekly_meetings', 'max_storage_mb', 'features', 'is_active',
            'is_public', 'display_order', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'yearly_discount_percentage', 'created_at', 'updated_at']


class SaccoSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Subscription"""
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    is_active_status = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    
    class Meta:
        model = SaccoSubscription
        fields = [
            'id', 'uuid', 'sacco', 'sacco_name', 'plan', 'plan_name', 'plan_details',
            'billing_cycle', 'start_date', 'end_date', 'trial_end_date', 'status',
            'auto_renew', 'cancel_at_period_end', 'next_billing_date',
            'last_payment_date', 'billing_email', 'billing_phone',
            'is_active_status', 'days_remaining', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'sacco_name', 'plan_name', 'plan_details',
            'is_active_status', 'days_remaining', 'created_at', 'updated_at'
        ]
    
    def get_is_active_status(self, obj):
        """Check if subscription is active"""
        return obj.is_active()
    
    def get_days_remaining(self, obj):
        """Get days until expiry"""
        return obj.days_until_expiry()


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Subscription Invoice"""
    sacco_name = serializers.CharField(source='subscription.sacco.name', read_only=True)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    
    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'uuid', 'subscription', 'sacco_name', 'plan_name',
            'invoice_number', 'invoice_date', 'due_date', 'amount', 'currency',
            'status', 'paid_date', 'payment_method', 'payment_reference',
            'period_start', 'period_end', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'sacco_name', 'plan_name', 'invoice_number',
            'invoice_date', 'created_at', 'updated_at'
        ]


class UsageMetricsSerializer(serializers.ModelSerializer):
    """Serializer for Usage Metrics"""
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    
    class Meta:
        model = UsageMetrics
        fields = [
            'id', 'uuid', 'sacco', 'sacco_name', 'period_start', 'period_end',
            'active_members_count', 'meetings_held', 'loans_created',
            'storage_used_mb', 'api_calls', 'total_contributions',
            'total_loans_disbursed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'sacco_name', 'created_at', 'updated_at']
