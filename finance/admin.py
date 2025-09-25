from django.contrib import admin
from finance.models import (
    Party, Account, Invoice, InvoiceItem, Payment, Transaction, Requisition, RequisitionDocument, RequisitionItem,
    PersonalTransaction, PersonalBudget, PersonalSavingsGoal, PersonalTransactionRecurring,
    PersonalAccountTransfer, PersonalDebt, PersonalLoan, DebtPayment, LoanRepayment
)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'email', 'phone')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('type',)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    readonly_fields = ('amount',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'party', 'direction', 'total', 'issue_date', 'due_date')
    search_fields = ('number', 'party__name')
    list_filter = ('direction', 'issue_date', 'due_date')
    inlines = [InvoiceItemInline]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'scope', 'owner', 'balance', 'currency', 'is_active')
    search_fields = ('name', 'number', 'owner__username')
    list_filter = ('type', 'scope', 'currency', 'is_active')
    readonly_fields = ('balance',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'direction', 'amount', 'party', 'invoice', 'account', 'method')
    search_fields = ('party__name', 'notes')
    list_filter = ('direction', 'method')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'amount', 'account', 'date', 'is_automated')
    list_filter = ('type', 'is_automated')
    search_fields = ('description',)


# Personal Finance Admin Classes

@admin.register(PersonalTransaction)
class PersonalTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'type', 'amount', 'account', 'description_short',
        'expense_category', 'income_source', 'date', 'is_recurring'
    )
    list_filter = (
        'type', 'expense_category', 'income_source', 'is_recurring',
        'date', 'account__type'
    )
    search_fields = (
        'description', 'reason', 'reference_number', 'location',
        'user__username', 'account__name'
    )
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'

    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'account')


@admin.register(PersonalBudget)
class PersonalBudgetAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'category', 'allocated_amount', 'spent_amount_display',
        'remaining_amount_display', 'progress_percentage_display', 'period', 'is_active'
    )
    list_filter = ('category', 'period', 'is_active', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'spent_amount', 'remaining_amount', 'progress_percentage')
    date_hierarchy = 'start_date'

    def spent_amount_display(self, obj):
        return f"{obj.spent_amount:.2f}"
    spent_amount_display.short_description = 'Spent'

    def remaining_amount_display(self, obj):
        return f"{obj.remaining_amount:.2f}"
    remaining_amount_display.short_description = 'Remaining'

    def progress_percentage_display(self, obj):
        return f"{obj.progress_percentage:.1f}%"
    progress_percentage_display.short_description = 'Progress'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(PersonalSavingsGoal)
class PersonalSavingsGoalAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'target_amount', 'current_amount',
        'remaining_amount_display', 'progress_percentage_display',
        'target_date', 'is_achieved'
    )
    list_filter = ('is_achieved', 'target_date', 'created_at')
    search_fields = ('name', 'description', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'remaining_amount', 'progress_percentage', 'is_achieved')
    date_hierarchy = 'target_date'

    def remaining_amount_display(self, obj):
        return f"{obj.remaining_amount:.2f}"
    remaining_amount_display.short_description = 'Remaining'

    def progress_percentage_display(self, obj):
        return f"{obj.progress_percentage:.1f}%"
    progress_percentage_display.short_description = 'Progress'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(PersonalTransactionRecurring)
class PersonalTransactionRecurringAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'user', 'type', 'amount', 'frequency', 
        'account', 'next_due_date', 'is_active'
    )
    list_filter = (
        'type', 'frequency', 'is_active', 'expense_category', 
        'income_source', 'next_due_date'
    )
    search_fields = ('name', 'description', 'user__username', 'account__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'next_due_date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'account')


# Account Transfer Admin
@admin.register(PersonalAccountTransfer)
class PersonalAccountTransferAdmin(admin.ModelAdmin):
    list_display = ('user', 'from_account', 'to_account', 'amount', 'transfer_fee', 'date')
    list_filter = ('user', 'date')
    search_fields = ('description', 'reference_number')
    readonly_fields = ('created_at', 'updated_at', 'total_debit_amount')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'from_account', 'to_account')


# Debt Payment Inline
class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0
    readonly_fields = ('created_at',)


# Loan Repayment Inline
class LoanRepaymentInline(admin.TabularInline):
    model = LoanRepayment
    extra = 0
    readonly_fields = ('created_at',)


# Debt Management Admin
@admin.register(PersonalDebt)
class PersonalDebtAdmin(admin.ModelAdmin):
    list_display = ('creditor_name', 'user', 'principal_amount', 'remaining_balance', 'due_date', 'is_active')
    list_filter = ('user', 'is_active', 'is_fully_paid', 'has_interest', 'due_date')
    search_fields = ('creditor_name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'remaining_balance', 'total_paid', 'is_overdue')
    inlines = [DebtPaymentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(PersonalLoan)
class PersonalLoanAdmin(admin.ModelAdmin):
    list_display = ('borrower_name', 'user', 'principal_amount', 'remaining_balance', 'due_date', 'is_active')
    list_filter = ('user', 'is_active', 'is_fully_repaid', 'has_interest', 'due_date')
    search_fields = ('borrower_name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'remaining_balance', 'total_repaid', 'is_overdue')
    inlines = [LoanRepaymentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(DebtPayment)
class DebtPaymentAdmin(admin.ModelAdmin):
    list_display = ('debt', 'amount', 'payment_date', 'account')
    list_filter = ('payment_date', 'debt__user')
    search_fields = ('debt__creditor_name', 'notes')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('debt', 'account')


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ('loan', 'amount', 'repayment_date', 'account')
    list_filter = ('repayment_date', 'loan__user')
    search_fields = ('loan__borrower_name', 'notes')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('loan', 'account')


# Requisition Admin Classes

class RequisitionDocumentInline(admin.TabularInline):
    model = RequisitionDocument
    extra = 0
    readonly_fields = ('uploaded_by', 'file_size', 'content_type', 'created_at')
    fields = ('file', 'filename', 'uploaded_by', 'file_size', 'content_type', 'created_at')


class RequisitionItemInline(admin.TabularInline):
    model = RequisitionItem
    extra = 1
    readonly_fields = ('amount',)
    fields = ('particular', 'quantity', 'unit_cost', 'amount')


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'purpose_short', 'requested_by', 'status', 'urgency', 
        'amount', 'effective_total', 'has_items', 'document_count', 'date_approved'
    )
    list_filter = ('status', 'urgency', 'has_items', 'created_at', 'date_approved')
    search_fields = ('purpose', 'comments', 'requested_by__username', 'approved_by__username')
    readonly_fields = ('calculated_total', 'effective_total', 'document_count', 'comment_count', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [RequisitionItemInline, RequisitionDocumentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('purpose', 'amount', 'urgency', 'status', 'comments')
        }),
        ('Users', {
            'fields': ('requested_by', 'approved_by', 'date_approved')
        }),
        ('Items & Calculations', {
            'fields': ('has_items', 'calculated_total', 'effective_total')
        }),
        ('Metadata', {
            'fields': ('document_count', 'comment_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def purpose_short(self, obj):
        return obj.purpose[:50] + '...' if len(obj.purpose) > 50 else obj.purpose
    purpose_short.short_description = 'Purpose'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requested_by', 'approved_by').prefetch_related('items', 'documents')


@admin.register(RequisitionDocument)
class RequisitionDocumentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'requisition_purpose', 'uploaded_by', 'file_size_display', 'created_at')
    list_filter = ('content_type', 'uploaded_by', 'created_at')
    search_fields = ('filename', 'requisition__purpose', 'uploaded_by__username')
    readonly_fields = ('file_size', 'content_type', 'created_at', 'updated_at')

    def requisition_purpose(self, obj):
        return obj.requisition.purpose[:30] + '...' if len(obj.requisition.purpose) > 30 else obj.requisition.purpose
    requisition_purpose.short_description = 'Requisition'

    def file_size_display(self, obj):
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = 'File Size'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requisition', 'uploaded_by')


@admin.register(RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = ('particular', 'requisition_purpose', 'quantity', 'unit_cost', 'amount')
    list_filter = ('requisition__status', 'requisition__urgency', 'created_at')
    search_fields = ('particular', 'requisition__purpose')
    readonly_fields = ('amount', 'created_at', 'updated_at')

    def requisition_purpose(self, obj):
        return obj.requisition.purpose[:30] + '...' if len(obj.requisition.purpose) > 30 else obj.requisition.purpose
    requisition_purpose.short_description = 'Requisition'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('requisition')
