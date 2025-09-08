from django.db import models
from django.utils import timezone
from core.models import BaseModel
from users.models import User
from common.enums import (
    PartyType, InvoiceDirection, TransactionType, AccountType, Currency,
    PriorityLevel, PaymentCategory, QuotationStatus, PaymentMethod
)
from django.db.models import Sum, F, DecimalField, Value as V
from django.db.models.functions import Coalesce


class Party(BaseModel):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    type = models.CharField(max_length=50, choices=PartyType.choices)
    is_internal_user = models.BooleanField(default=False)
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Account(BaseModel):
    name = models.CharField(max_length=100)
    number = models.CharField(max_length=20, blank=True)
    type = models.CharField(max_length=50, choices=AccountType.choices)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.Uganda)

    def __str__(self):
        return f"{self.name} ({self.type})"

    @property
    def incoming_transactions(self):
        return self.transaction_set.filter(type=TransactionType.INCOME)

    @property
    def outgoing_transactions(self):
        return self.transaction_set.filter(type=TransactionType.EXPENSE)

    def update_balance(self):
        income = self.incoming_transactions.aggregate(total=Sum('amount'))['total'] or 0
        expense = self.outgoing_transactions.aggregate(total=Sum('amount'))['total'] or 0
        self.balance = income - expense
        self.save(update_fields=['balance'])

    def apply_transaction(self, tx_type, amount):
        if tx_type == TransactionType.INCOME:
            self.balance += amount
        else:
            self.balance -= amount
        self.save(update_fields=['balance'])


def invoice_upload_path(instance, filename):
    # e.g. invoices/2025/party_<id>/<number>.pdf
    year = timezone.now().year
    pid = instance.party_id or 'unknown'
    return f"invoices/{year}/party_{pid}/{filename}"


class InvoiceQuerySet(models.QuerySet):
    def with_paid_and_due(self):
        return self.annotate(
            paid_amount_agg=Coalesce(
                Sum('payments__amount'),
                V(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ).annotate(
            amount_due=F('total') - F('paid_amount_agg')
        )

    def unpaid(self):
        return self.with_paid_and_due().filter(amount_due__gt=0)


class Invoice(BaseModel):
    party = models.ForeignKey('finance.Party', related_name='invoices', on_delete=models.PROTECT)
    direction = models.CharField(max_length=20, choices=InvoiceDirection.choices)
    number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.Uganda)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    document = models.FileField(upload_to=invoice_upload_path, blank=True, null=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ('-issue_date', '-id')

    @property
    def paid_amount(self):
        return self.payments.aggregate(
            total=Coalesce(Sum('amount'), V(0, output_field=DecimalField(max_digits=12, decimal_places=2)))
        )['total']

    @property
    def amount_due(self):
        return max(self.total - (self.paid_amount or 0), 0)

    def update_total(self):
        items_total = self.items.aggregate(total=Sum('amount'))['total'] or 0
        if self.items.exists():
            self.subtotal = items_total
            self.total = (self.subtotal + self.tax) - self.discount
            self.save(update_fields=['subtotal', 'total'])


class Goal(BaseModel):
    title = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True)

    def update_progress(self):
        total = self.payments.filter(direction='incoming').aggregate(total=Sum('amount'))['total'] or 0
        self.current_amount = total
        self.save(update_fields=['current_amount'])
        self.check_milestones()

    def check_milestones(self):
        for milestone in self.milestones.filter(notify=True, is_reached=False):
            if self.current_amount >= milestone.amount:
                milestone.is_reached = True
                milestone.save(update_fields=['is_reached'])


class GoalMilestone(models.Model):
    goal = models.ForeignKey(Goal, related_name='milestones', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notify = models.BooleanField(default=True)
    is_reached = models.BooleanField(default=False)


class Requisition(BaseModel):
    requested_by = models.ForeignKey(User, related_name='requested_requisitions', on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(User, related_name='approved_requisitions', null=True, blank=True, on_delete=models.SET_NULL)
    urgency = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    status = models.CharField(max_length=20, default='pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.TextField()
    comments = models.TextField(blank=True)
    date_approved = models.DateField(null=True, blank=True)


    def approve(self, user: User):
        self.approved_by = user
        self.status = 'approved'
        self.date_approved = timezone.now().date()
        self.save()


class Payment(BaseModel):
    direction = models.CharField(
        max_length=10,
        choices=(('incoming', 'Incoming'), ('outgoing', 'Outgoing'))
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, null=True, blank=True, related_name='payments', on_delete=models.SET_NULL)
    requisition = models.OneToOneField(Requisition, null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    transaction = models.OneToOneField(
        'Transaction', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_payment'
    )
    receipt_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    goal = models.ForeignKey(Goal, null=True, blank=True, related_name='payments', on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        # Keep Payment side-effects minimal; FinanceService handles transactions and invoice state
        super().save(*args, **kwargs)


class Transaction(BaseModel):
    type = models.CharField(max_length=20, choices=TransactionType.choices)  # income, expense
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    category = models.CharField(max_length=50, choices=PaymentCategory.choices)

    related_invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL)
    related_requisition = models.ForeignKey(Requisition, null=True, blank=True, on_delete=models.SET_NULL)
    related_payment = models.OneToOneField(
        'Payment', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_transaction'
    )

    date = models.DateField(default=timezone.now)
    is_automated = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)
        if creating and self.account:
            self.account.apply_transaction(self.type, self.amount)


class Quotation(BaseModel):
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    quote_number = models.CharField(max_length=50, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    issued_date = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)
    related_file = models.FileField(upload_to='quotations/', blank=True, null=True)

    def __str__(self):
        return f"Quotation #{self.quote_number or self.id} - {self.party.name}"

    def update_total(self):
        total = self.items.aggregate(total=Sum('amount'))['total'] or 0
        self.total_amount = total
        self.save(update_fields=['total_amount'])


class Receipt(BaseModel):
    number = models.CharField(max_length=50, blank=True)
    date = models.DateField(default=timezone.now)
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to='receipts/official/', null=True, blank=True)
    notes = models.TextField(blank=True)
    payment = models.OneToOneField('Payment', null=True, blank=True, on_delete=models.SET_NULL, related_name='receipt')

    def __str__(self):
        return f"Receipt {self.number or self.id} - {self.party.name}"

    def update_total(self):
        total = self.items.aggregate(total=Sum('amount'))['total'] or 0
        self.amount = total
        self.save(update_fields=['amount'])


class InvoiceItem(BaseModel):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        # Amount derived from quantity * unit_cost
        self.amount = (self.quantity or 0) * (self.unit_cost or 0)
        super().save(*args, **kwargs)
        # Update parent invoice total
        self.invoice.update_total()


class QuotationItem(BaseModel):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or 0) * (self.unit_cost or 0)
        super().save(*args, **kwargs)
        self.quotation.update_total()


class ReceiptItem(BaseModel):
    receipt = models.ForeignKey(Receipt, related_name='items', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.quantity or 0) * (self.unit_cost or 0)
        super().save(*args, **kwargs)
        self.receipt.update_total()
