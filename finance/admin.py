from django.contrib import admin
from finance.models import (
    Party, Account, Invoice, Payment, Transaction,
    Goal, GoalMilestone, Requisition,
    Quotation, Receipt,
    InvoiceItem, QuotationItem, ReceiptItem,
)


class GoalMilestoneInline(admin.TabularInline):
    model = GoalMilestone
    extra = 1


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'email', 'phone', 'is_internal_user', 'linked_user')
    search_fields = ('name', 'email', 'phone')
    list_filter = ('type', 'is_internal_user')

    def linked_user(self, obj):
        if obj.user:
            return admin.utils.format_html('<a href="/admin/users/user/{}/change/">{}</a>', obj.user.id, obj.user.username)
        return '-'
    linked_user.short_description = 'User'


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'type', 'balance', 'currency')
    search_fields = ('name', 'number')
    list_filter = ('type', 'currency')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'party_link', 'direction', 'total_amount', 'issued_date', 'due_date', 'is_paid')
    list_filter = ('direction', 'is_paid')
    search_fields = ('party__name', 'description')
    date_hierarchy = 'issued_date'
    autocomplete_fields = ('party',)
    inlines = []

    def party_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/party/{}/change/">{}</a>', obj.party.id, obj.party.name)
    party_link.short_description = 'Party'


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('name', 'description', 'quantity', 'unit_cost', 'amount')
    readonly_fields = ('amount',)


InvoiceAdmin.inlines.append(InvoiceItemInline)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'direction', 'amount', 'party_link', 'account', 'invoice_link', 'requisition_link', 'goal', 'receipt_link')
    list_filter = ('direction', 'goal')
    search_fields = ('party__name', 'notes')
    autocomplete_fields = ('party', 'account', 'invoice', 'requisition', 'goal')

    def party_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/party/{}/change/">{}</a>', obj.party.id, obj.party.name)

    def invoice_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/invoice/{}/change/">Invoice #{}</a>', obj.invoice.id, obj.invoice.id) if obj.invoice else '-'

    def requisition_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/requisition/{}/change/">Requisition #{}</a>', obj.requisition.id, obj.requisition.id) if obj.requisition else '-'

    party_link.short_description = 'Party'
    invoice_link.short_description = 'Invoice'
    requisition_link.short_description = 'Requisition'
    def receipt_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/receipt/{}/change/">Receipt #{}</a>', obj.receipt.id, obj.receipt.id) if hasattr(obj, 'receipt') and obj.receipt else '-'
    receipt_link.short_description = 'Receipt'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'amount', 'account', 'date', 'is_automated', 'payment_link')
    list_filter = ('type', 'is_automated')
    search_fields = ('description',)
    date_hierarchy = 'date'
    autocomplete_fields = ('account', 'related_invoice', 'related_payment', 'related_requisition')

    def payment_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/payment/{}/change/">Payment #{}</a>', obj.related_payment.id, obj.related_payment.id) if obj.related_payment else '-'
    payment_link.short_description = 'Payment'


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'target_amount', 'current_amount', 'due_date')
    search_fields = ('title', 'owner__username')
    list_filter = ('due_date',)
    autocomplete_fields = ('owner',)
    inlines = [GoalMilestoneInline]


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ('id', 'requested_by', 'approved_by', 'urgency', 'status', 'amount')
    list_filter = ('status', 'urgency')
    search_fields = ('purpose', 'comments')
    autocomplete_fields = ('requested_by', 'approved_by')


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('id', 'quote_number', 'party_link', 'total_amount', 'status', 'issued_date', 'valid_until')
    list_filter = ('status',)
    search_fields = ('quote_number', 'party__name', 'description')
    autocomplete_fields = ('party',)
    inlines = []

    def party_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/party/{}/change/">{}</a>', obj.party.id, obj.party.name)
    party_link.short_description = 'Party'


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1
    fields = ('name', 'description', 'quantity', 'unit_cost', 'amount')
    readonly_fields = ('amount',)


QuotationAdmin.inlines.append(QuotationItemInline)


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'party_link', 'amount', 'date', 'method', 'invoice_link')
    list_filter = ('method',)
    search_fields = ('number', 'party__name', 'reference', 'notes')
    autocomplete_fields = ('party', 'invoice', 'account', 'payment')
    inlines = []

    def party_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/party/{}/change/">{}</a>', obj.party.id, obj.party.name)

    def invoice_link(self, obj):
        return admin.utils.format_html('<a href="/admin/finance/invoice/{}/change/">Invoice #{}</a>', obj.invoice.id, obj.invoice.id) if obj.invoice else '-'

    party_link.short_description = 'Party'
    invoice_link.short_description = 'Invoice'


class ReceiptItemInline(admin.TabularInline):
    model = ReceiptItem
    extra = 1
    fields = ('name', 'description', 'quantity', 'unit_cost', 'amount')
    readonly_fields = ('amount',)


ReceiptAdmin.inlines.append(ReceiptItemInline)
