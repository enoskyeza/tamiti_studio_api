from django.contrib import admin
from .models import (
    SaccoOrganization,
    SaccoMember,
    MemberPassbook,
    PassbookSection,
    PassbookEntry,
    DeductionRule,
    CashRound,
    CashRoundMember,
    CashRoundSchedule,
    WeeklyMeeting,
    WeeklyContribution,
    SaccoLoan,
    LoanPayment,
    LoanGuarantor,
    SaccoEmergencySupport,
    SaccoWithdrawal,
    WithdrawalAllocation,
    SubscriptionPlan,
    SaccoSubscription,
    SubscriptionInvoice,
    UsageMetrics
)


@admin.register(SaccoOrganization)
class SaccoOrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'registration_number', 'member_count', 'is_active', 'subscription_status', 'created_at']
    list_filter = ['is_active', 'subscription_status', 'created_at']
    search_fields = ['name', 'registration_number', 'email']
    filter_horizontal = ['admins']
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'member_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'registration_number', 'description')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Cash Round Configuration', {
            'fields': ('cash_round_amount', 'meeting_day')
        }),
        ('Status & Subscription', {
            'fields': ('is_active', 'subscription_plan', 'subscription_status', 'subscription_expires_at')
        }),
        ('Administration', {
            'fields': ('admins',)
        }),
        ('Configuration', {
            'fields': ('settings',),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SaccoWithdrawal)
class SaccoWithdrawalAdmin(admin.ModelAdmin):
    list_display = ['withdrawal_number', 'sacco', 'member', 'amount', 'status', 'request_date', 'approval_date', 'disbursement_date']
    list_filter = ['sacco', 'status', 'request_date', 'approval_date']
    search_fields = ['withdrawal_number', 'member__member_number', 'member__user__first_name', 'member__user__last_name']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(WithdrawalAllocation)
class WithdrawalAllocationAdmin(admin.ModelAdmin):
    list_display = ['withdrawal', 'section', 'amount', 'passbook_entry', 'created_at']
    list_filter = ['section']
    search_fields = ['withdrawal__withdrawal_number', 'section__name']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(SaccoMember)
class SaccoMemberAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id_display', 'member_number', 'user', 'sacco', 'role', 'status', 'date_joined']
    list_filter = ['status', 'sacco', 'role', 'is_secretary', 'is_treasurer', 'is_chairperson', 'date_joined']
    search_fields = ['member_number', 'user__username', 'user__first_name', 'user__last_name', 'national_id']
    readonly_fields = ['uuid', 'date_joined', 'created_at', 'updated_at']

    def user_id_display(self, obj):
        return obj.user_id

    user_id_display.short_description = 'User ID'
    user_id_display.admin_order_field = 'user_id'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'sacco', 'member_number', 'passbook_number', 'status')
        }),
        ('Personal Details', {
            'fields': ('national_id', 'date_of_birth', 'occupation', 'address', 'alternative_phone')
        }),
        ('Next of Kin', {
            'fields': ('next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship')
        }),
        ('Savings Goal', {
            'fields': ('savings_goal', 'savings_goal_deadline'),
            'description': 'Set personal savings targets for the member'
        }),
        ('Roles', {
            'fields': ('role', 'is_secretary', 'is_treasurer', 'is_chairperson')
        }),
        ('Dates', {
            'fields': ('date_joined', 'date_left')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MemberPassbook)
class MemberPassbookAdmin(admin.ModelAdmin):
    list_display = ['passbook_number', 'member', 'sacco', 'is_active', 'issued_date']
    list_filter = ['is_active', 'sacco', 'issued_date']
    search_fields = ['passbook_number', 'member__member_number', 'member__user__username']
    readonly_fields = ['uuid', 'issued_date', 'created_at', 'updated_at']


@admin.register(PassbookSection)
class PassbookSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'sacco', 'section_type', 'is_compulsory', 'withdrawable', 'weekly_amount', 'display_order', 'is_active']
    list_filter = ['sacco', 'section_type', 'is_compulsory', 'withdrawable', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    ordering = ['sacco', 'display_order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sacco', 'name', 'section_type', 'description')
        }),
        ('Configuration', {
            'fields': ('is_compulsory', 'withdrawable', 'weekly_amount', 'allow_variable_amounts')
        }),
        ('Display', {
            'fields': ('display_order', 'is_active', 'color')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PassbookEntry)
class PassbookEntryAdmin(admin.ModelAdmin):
    list_display = ['passbook', 'section', 'transaction_date', 'transaction_type', 'amount', 'balance_after', 'meeting', 'week_number', 'recorded_by']
    list_filter = ['transaction_type', 'transaction_date', 'section', 'meeting', 'is_reversal']
    search_fields = ['passbook__passbook_number', 'passbook__member__member_number', 'description', 'reference_number']
    readonly_fields = ['uuid', 'balance_after', 'created_at', 'updated_at']
    date_hierarchy = 'transaction_date'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('passbook', 'section', 'transaction_date', 'transaction_type', 'amount', 'balance_after')
        }),
        ('Meeting Link', {
            'fields': ('meeting', 'week_number')
        }),
        ('Description & Reference', {
            'fields': ('description', 'reference_number')
        }),
        ('Audit', {
            'fields': ('recorded_by',)
        }),
        ('Reversal', {
            'fields': ('is_reversal', 'reverses_entry'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeductionRule)
class DeductionRuleAdmin(admin.ModelAdmin):
    list_display = ['sacco', 'section', 'amount', 'applies_to', 'is_active', 'effective_from', 'effective_until']
    list_filter = ['sacco', 'applies_to', 'is_active', 'effective_from']
    search_fields = ['description']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sacco', 'section', 'amount', 'applies_to')
        }),
        ('Effectiveness', {
            'fields': ('is_active', 'effective_from', 'effective_until')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
# This file contains admin registrations for Phase 3 and 4
# Append this content to saccos/admin.py

# ============================================================================
# PHASE 3: WEEKLY MEETINGS ADMIN
# ============================================================================


@admin.register(CashRound)
class CashRoundAdmin(admin.ModelAdmin):
    list_display = ['name', 'sacco', 'round_number', 'status', 'start_date', 'expected_end_date', 'created_by']
    list_filter = ['status', 'sacco', 'start_date']
    search_fields = ['name', 'sacco__name']
    readonly_fields = ['uuid', 'round_number', 'started_at', 'completed_at', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sacco', 'name', 'round_number', 'status')
        }),
        ('Schedule', {
            'fields': ('start_date', 'expected_end_date', 'actual_end_date', 'num_weeks')
        }),
        ('Configuration', {
            'fields': ('weekly_amount',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'started_at', 'completed_at', 'notes')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class CashRoundMemberInline(admin.TabularInline):
    model = CashRoundMember
    extra = 0
    fields = ['member', 'position_in_rotation', 'is_active', 'joined_at', 'left_at']
    readonly_fields = ['joined_at']


@admin.register(CashRoundMember)
class CashRoundMemberAdmin(admin.ModelAdmin):
    list_display = ['cash_round', 'member', 'position_in_rotation', 'is_active', 'joined_at']
    list_filter = ['is_active', 'cash_round__sacco', 'joined_at']
    search_fields = ['member__user__first_name', 'member__user__last_name', 'cash_round__name']
    readonly_fields = ['uuid', 'joined_at', 'created_at', 'updated_at']


@admin.register(CashRoundSchedule)
class CashRoundScheduleAdmin(admin.ModelAdmin):
    list_display = ['cash_round', 'sacco', 'start_date', 'end_date', 'current_position', 'is_active', 'created_at']
    list_filter = ['is_active', 'sacco', 'start_date']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(WeeklyMeeting)
class WeeklyMeetingAdmin(admin.ModelAdmin):
    list_display = ['cash_round', 'sacco', 'meeting_date', 'week_number', 'year', 'cash_round_recipient', 'status', 'total_collected']
    list_filter = ['status', 'cash_round', 'sacco', 'year', 'meeting_date']
    search_fields = ['cash_round_recipient__member_number', 'cash_round_recipient__user__username', 'cash_round__name']
    readonly_fields = ['uuid', 'week_number', 'year', 'created_at', 'updated_at']
    date_hierarchy = 'meeting_date'


@admin.register(WeeklyContribution)
class WeeklyContributionAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'member', 'was_present', 'amount_contributed', 'optional_savings', 'is_recipient', 'total_deductions']
    list_filter = ['was_present', 'is_recipient', 'meeting__sacco']
    search_fields = ['member__member_number', 'member__user__username']
    readonly_fields = ['uuid', 'created_at', 'updated_at']


# ============================================================================
# PHASE 4: LOAN MANAGEMENT ADMIN
# ============================================================================


@admin.register(SaccoLoan)
class SaccoLoanAdmin(admin.ModelAdmin):
    list_display = ['loan_number', 'member', 'principal_amount', 'interest_rate', 'status', 'application_date', 'due_date']
    list_filter = ['status', 'sacco', 'application_date']
    search_fields = ['loan_number', 'member__member_number', 'member__user__username']
    readonly_fields = ['uuid', 'loan_number', 'interest_amount', 'total_amount', 'amount_paid_principal', 
                      'amount_paid_interest', 'balance_principal', 'balance_interest', 'created_at', 'updated_at']
    date_hierarchy = 'application_date'
    
    fieldsets = (
        ('Loan Information', {
            'fields': ('sacco', 'member', 'loan_number', 'status')
        }),
        ('Amounts', {
            'fields': ('principal_amount', 'interest_rate', 'interest_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('application_date', 'approval_date', 'disbursement_date', 'due_date', 'duration_months')
        }),
        ('Payment Tracking', {
            'fields': ('amount_paid_principal', 'amount_paid_interest', 'balance_principal', 'balance_interest')
        }),
        ('Purpose & Notes', {
            'fields': ('purpose', 'notes')
        }),
        ('Approval', {
            'fields': ('approved_by', 'rejection_reason')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LoanPayment)
class LoanPaymentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'payment_date', 'total_amount', 'principal_amount', 'interest_amount', 'recorded_by']
    list_filter = ['payment_date', 'loan__sacco']
    search_fields = ['loan__loan_number', 'reference_number']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    date_hierarchy = 'payment_date'


@admin.register(LoanGuarantor)
class LoanGuarantorAdmin(admin.ModelAdmin):
    list_display = ['loan', 'guarantor', 'guarantee_amount', 'guarantee_date', 'is_active']
    list_filter = ['is_active', 'guarantee_date']
    search_fields = ['loan__loan_number', 'guarantor__member_number']
    readonly_fields = ['uuid', 'guarantee_date', 'created_at', 'updated_at']


@admin.register(SaccoEmergencySupport)
class SaccoEmergencySupportAdmin(admin.ModelAdmin):
    list_display = ['member', 'support_date', 'amount', 'status', 'approved_by']
    list_filter = ['status', 'sacco', 'support_date']
    search_fields = ['member__member_number', 'member__user__username', 'reason']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    date_hierarchy = 'support_date'
# Admin registrations for Phase 6 - Append to admin.py

# ============================================================================
# PHASE 6: SAAS FEATURES ADMIN
# ============================================================================


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'monthly_price', 'yearly_price', 'max_members', 'is_active', 'is_public', 'display_order']
    list_filter = ['is_active', 'is_public']
    search_fields = ['name', 'description']
    readonly_fields = ['uuid', 'yearly_discount_percentage', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Plan Details', {
            'fields': ('name', 'description', 'display_order')
        }),
        ('Pricing', {
            'fields': ('monthly_price', 'yearly_price', 'currency', 'yearly_discount_percentage')
        }),
        ('Limits', {
            'fields': ('max_members', 'max_weekly_meetings', 'max_storage_mb')
        }),
        ('Features', {
            'fields': ('features',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_public')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SaccoSubscription)
class SaccoSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['sacco', 'plan', 'billing_cycle', 'status', 'start_date', 'end_date', 'auto_renew']
    list_filter = ['status', 'billing_cycle', 'auto_renew', 'plan']
    search_fields = ['sacco__name', 'billing_email']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Subscription', {
            'fields': ('sacco', 'plan', 'billing_cycle', 'status')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'trial_end_date', 'next_billing_date', 'last_payment_date')
        }),
        ('Settings', {
            'fields': ('auto_renew', 'cancel_at_period_end')
        }),
        ('Billing Contact', {
            'fields': ('billing_email', 'billing_phone')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'subscription', 'amount', 'currency', 'status', 'invoice_date', 'due_date']
    list_filter = ['status', 'invoice_date']
    search_fields = ['invoice_number', 'subscription__sacco__name', 'payment_reference']
    readonly_fields = ['uuid', 'invoice_number', 'invoice_date', 'created_at', 'updated_at']
    date_hierarchy = 'invoice_date'
    
    fieldsets = (
        ('Invoice', {
            'fields': ('subscription', 'invoice_number', 'invoice_date', 'due_date')
        }),
        ('Amount', {
            'fields': ('amount', 'currency')
        }),
        ('Payment', {
            'fields': ('status', 'paid_date', 'payment_method', 'payment_reference')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UsageMetrics)
class UsageMetricsAdmin(admin.ModelAdmin):
    list_display = ['sacco', 'period_start', 'period_end', 'active_members_count', 'meetings_held', 'loans_created']
    list_filter = ['period_start', 'sacco']
    search_fields = ['sacco__name']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Period', {
            'fields': ('sacco', 'period_start', 'period_end')
        }),
        ('Usage Counts', {
            'fields': ('active_members_count', 'meetings_held', 'loans_created', 'storage_used_mb', 'api_calls')
        }),
        ('Financial Metrics', {
            'fields': ('total_contributions', 'total_loans_disbursed')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
