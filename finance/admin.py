from django.contrib import admin
from finance.models import Party, Account, Invoice, InvoiceItem, Payment, Transaction


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
    list_display = ('name', 'type', 'balance', 'currency')
    search_fields = ('name', 'number')
    list_filter = ('type', 'currency')


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
