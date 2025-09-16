from django.db import models
from django.utils import timezone
from core.models import BaseModel
from users.models import User
from common.enums import (
    PartyType, InvoiceDirection, TransactionType, AccountType, Currency,
    PriorityLevel, PaymentCategory, QuotationStatus, PaymentMethod,
    FinanceScope, PersonalExpenseCategory, PersonalIncomeSource, BudgetPeriod
)
from django.db.models import Sum, F, DecimalField, Value as V
from django.db.models.functions import Coalesce
from django.core.validators import MinValueValidator
from decimal import Decimal


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
    scope = models.CharField(max_length=20, choices=FinanceScope.choices, default=FinanceScope.COMPANY)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                             help_text="Required for personal accounts")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.Uganda)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, help_text="Additional account details")

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(scope='company') | (models.Q(scope='personal') & models.Q(owner__isnull=False)),
                name='personal_accounts_must_have_owner'
            )
        ]

    def __str__(self):
        scope_prefix = f"[{self.get_scope_display()}] " if self.scope == FinanceScope.PERSONAL else ""
        return f"{scope_prefix}{self.name} ({self.type})"

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


class PersonalTransaction(BaseModel):
    """
    Enhanced transaction model for personal finance tracking with detailed insights
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_transactions')
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    account = models.ForeignKey(Account, on_delete=models.CASCADE,
                               limit_choices_to={'scope': FinanceScope.PERSONAL})

    # Core transaction details
    description = models.TextField(help_text="Detailed description of the transaction")
    transaction_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           validators=[MinValueValidator(Decimal('0'))],
                                           help_text="Fees/charges associated with this transaction")

    # Income specific fields
    income_source = models.CharField(max_length=50, choices=PersonalIncomeSource.choices, blank=True,
                                   help_text="Required for income transactions")

    # Expense specific fields
    expense_category = models.CharField(max_length=50, choices=PersonalExpenseCategory.choices, blank=True,
                                      help_text="Required for expense transactions")

    # Common metadata
    reason = models.TextField(help_text="Reason/purpose for this transaction")
    date = models.DateTimeField(default=timezone.now, db_index=True)
    reference_number = models.CharField(max_length=100, blank=True,
                                      help_text="Bank reference, receipt number, etc.")
    receipt_image = models.ImageField(upload_to='personal_receipts/%Y/%m/', blank=True, null=True)

    # Enhanced tracking
    tags = models.JSONField(default=list, blank=True,
                           help_text="Custom tags for categorization and search")
    location = models.CharField(max_length=200, blank=True, help_text="Where the transaction occurred")
    notes = models.TextField(blank=True, help_text="Additional notes")

    # System fields
    is_recurring = models.BooleanField(default=False)
    recurring_parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='recurring_instances')

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'type', 'date']),
            models.Index(fields=['user', 'expense_category']),
            models.Index(fields=['account', 'date']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.type == TransactionType.INCOME and not self.income_source:
            raise ValidationError({'income_source': 'Income source is required for income transactions'})

        if self.type == TransactionType.EXPENSE and not self.expense_category:
            raise ValidationError({'expense_category': 'Expense category is required for expense transactions'})

        if self.account and self.account.owner != self.user:
            raise ValidationError({'account': 'Account must belong to the transaction user'})

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new and self.account:
            self.account.apply_transaction(self.type, self.amount)

    @property
    def total_cost(self):
        """Total cost including transaction charges"""
        return self.amount + self.transaction_charge

    def __str__(self):
        return f"{self.get_type_display()}: {self.amount} - {self.description[:50]}"


class PersonalBudget(BaseModel):
    """
    Budget management for personal expense categories
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_budgets')
    name = models.CharField(max_length=100, help_text="Budget name/title")
    category = models.CharField(max_length=50, choices=PersonalExpenseCategory.choices)
    period = models.CharField(max_length=20, choices=BudgetPeriod.choices, default=BudgetPeriod.MONTHLY)

    # Budget amounts
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    spent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     validators=[MinValueValidator(Decimal('0'))])

    # Period tracking
    start_date = models.DateField()
    end_date = models.DateField()

    # Settings
    is_active = models.BooleanField(default=True)
    alert_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80,
                                        help_text="Alert when spent percentage reaches this threshold")

    class Meta:
        unique_together = ['user', 'category', 'start_date']
        ordering = ['-start_date', 'category']

    @property
    def remaining_amount(self):
        return max(self.allocated_amount - self.spent_amount, Decimal('0'))

    @property
    def progress_percentage(self):
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return Decimal('0')

    @property
    def is_exceeded(self):
        return self.spent_amount > self.allocated_amount

    @property
    def should_alert(self):
        return self.progress_percentage >= self.alert_threshold

    def update_spent_amount(self):
        """Recalculate spent amount from transactions"""
        total = PersonalTransaction.objects.filter(
            user=self.user,
            type=TransactionType.EXPENSE,
            expense_category=self.category,
            date__range=[self.start_date, self.end_date]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        self.spent_amount = total
        self.save(update_fields=['spent_amount'])

    def __str__(self):
        return f"{self.name} - {self.get_category_display()} ({self.get_period_display()})"


class PersonalSavingsGoal(BaseModel):
    """
    Savings goal tracking with milestone support
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Goal amounts
    target_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                      validators=[MinValueValidator(Decimal('0.01'))])
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       validators=[MinValueValidator(Decimal('0'))])

    # Timeline
    target_date = models.DateField()
    created_date = models.DateField(auto_now_add=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_achieved = models.BooleanField(default=False)
    achieved_date = models.DateField(null=True, blank=True)

    # Settings
    auto_save_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         help_text="Automatic savings amount per period")
    auto_save_frequency = models.CharField(max_length=20, choices=BudgetPeriod.choices,
                                         default=BudgetPeriod.MONTHLY, blank=True)

    class Meta:
        ordering = ['-created_date']

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, 100)
        return Decimal('0')

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.current_amount, Decimal('0'))

    @property
    def days_remaining(self):
        if self.target_date:
            delta = self.target_date - timezone.now().date()
            return max(delta.days, 0)
        return 0

    @property
    def required_monthly_savings(self):
        """Calculate required monthly savings to reach goal"""
        if self.days_remaining > 0:
            months_remaining = max(self.days_remaining / 30, 1)
            return self.remaining_amount / Decimal(str(months_remaining))
        return Decimal('0')

    def add_contribution(self, amount, description="Manual contribution"):
        """Add a contribution to this savings goal"""
        self.current_amount += amount
        if self.current_amount >= self.target_amount and not self.is_achieved:
            self.is_achieved = True
            self.achieved_date = timezone.now().date()
        self.save()

        # Create a savings transaction
        PersonalTransaction.objects.create(
            user=self.user,
            type=TransactionType.EXPENSE,
            amount=amount,
            account=self.user.account_set.filter(scope=FinanceScope.PERSONAL).first(),
            expense_category=PersonalExpenseCategory.SAVINGS,
            description=f"Savings for: {self.name}",
            reason=description
        )

    def __str__(self):
        return f"{self.name} - {self.progress_percentage:.1f}% complete"


class PersonalTransactionRecurring(BaseModel):
    """
    Template for recurring personal transactions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    name = models.CharField(max_length=200, help_text="Name for this recurring transaction")

    # Transaction details
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    description = models.TextField()

    # Recurring settings
    frequency = models.CharField(max_length=20, choices=BudgetPeriod.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for indefinite")

    # Category based on type
    income_source = models.CharField(max_length=50, choices=PersonalIncomeSource.choices, blank=True)
    expense_category = models.CharField(max_length=50, choices=PersonalExpenseCategory.choices, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    next_due_date = models.DateField()
    last_created_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['next_due_date']

    def create_next_transaction(self):
        """Create the next instance of this recurring transaction"""
        if not self.is_active or (self.end_date and timezone.now().date() > self.end_date):
            return None

        transaction = PersonalTransaction.objects.create(
            user=self.user,
            type=self.type,
            amount=self.amount,
            account=self.account,
            description=self.description,
            income_source=self.income_source,
            expense_category=self.expense_category,
            reason=f"Recurring: {self.name}",
            is_recurring=True,
            recurring_parent=None
        )

        # Update next due date
        self.last_created_date = timezone.now().date()
        if self.frequency == BudgetPeriod.WEEKLY:
            self.next_due_date += timezone.timedelta(weeks=1)
        elif self.frequency == BudgetPeriod.MONTHLY:
            self.next_due_date += timezone.timedelta(days=30)
        elif self.frequency == BudgetPeriod.QUARTERLY:
            self.next_due_date += timezone.timedelta(days=90)
        elif self.frequency == BudgetPeriod.YEARLY:
            self.next_due_date += timezone.timedelta(days=365)

        self.save()
        return transaction

    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"


class PersonalAccountTransfer(BaseModel):
    """
    Transfer funds between personal accounts with fee tracking
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='account_transfers')

    # Transfer details
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='outgoing_transfers',
                                   limit_choices_to={'scope': FinanceScope.PERSONAL})
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='incoming_transfers',
                                 limit_choices_to={'scope': FinanceScope.PERSONAL})
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    # Fees and charges
    transfer_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     validators=[MinValueValidator(Decimal('0'))])
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1,
                                      help_text="For different currency accounts")

    # Metadata
    description = models.TextField()
    reference_number = models.CharField(max_length=100, blank=True)
    date = models.DateTimeField(default=timezone.now)

    # Linked transactions (automatically created)
    debit_transaction = models.OneToOneField(PersonalTransaction, on_delete=models.CASCADE,
                                           related_name='transfer_debit', null=True, blank=True)
    credit_transaction = models.OneToOneField(PersonalTransaction, on_delete=models.CASCADE,
                                            related_name='transfer_credit', null=True, blank=True)
    fee_transaction = models.OneToOneField(PersonalTransaction, on_delete=models.CASCADE,
                                         related_name='transfer_fee', null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.from_account == self.to_account:
            raise ValidationError("Cannot transfer to the same account")

        if self.from_account.owner != self.user or self.to_account.owner != self.user:
            raise ValidationError("Both accounts must belong to the user")

    @property
    def total_debit_amount(self):
        """Total amount debited from source account (amount + fee)"""
        return (self.amount or Decimal('0')) + (self.transfer_fee or Decimal('0'))

    def __str__(self):
        return f"Transfer: {self.amount} from {self.from_account.name} to {self.to_account.name}"


class PersonalDebt(BaseModel):
    """
    Track personal debts owed to others
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_debts')

    # Creditor details
    creditor_name = models.CharField(max_length=200)
    creditor_contact = models.CharField(max_length=100, blank=True)

    # Debt amounts
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    current_balance = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0'))])

    # Interest and terms
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      validators=[MinValueValidator(Decimal('0'))],
                                      help_text="Annual interest rate percentage")
    has_interest = models.BooleanField(default=False)

    # Dates
    borrowed_date = models.DateField()
    due_date = models.DateField()

    # Status
    is_active = models.BooleanField(default=True)
    is_fully_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['due_date', '-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(creditor_name__isnull=False) & ~models.Q(creditor_name=''),
                name='debt_creditor_name_not_empty'
            ),
            models.CheckConstraint(
                check=models.Q(due_date__gte=models.F('borrowed_date')),
                name='debt_due_date_after_borrowed_date'
            ),
        ]

    @property
    def total_paid(self):
        return self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    @property
    def remaining_balance(self):
        return max(self.current_balance - self.total_paid, Decimal('0'))

    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and not self.is_fully_paid

    def make_payment(self, amount, account, notes=""):
        """Make a payment towards this debt"""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        payment = DebtPayment.objects.create(
            debt=self,
            amount=amount,
            account=account,
            notes=notes
        )

        # Check if debt is fully paid
        if self.remaining_balance <= 0:
            self.is_fully_paid = True
            self.paid_date = timezone.now().date()
            self.is_active = False
            self.save()

        return payment

    def __str__(self):
        return f"Debt to {self.creditor_name}: {self.remaining_balance}/{self.principal_amount}"


class PersonalLoan(BaseModel):
    """
    Track personal loans given to others
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_loans')

    # Borrower details
    borrower_name = models.CharField(max_length=200)
    borrower_contact = models.CharField(max_length=100, blank=True)

    # Loan amounts
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    current_balance = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0'))])

    # Interest and terms
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      validators=[MinValueValidator(Decimal('0'))],
                                      help_text="Annual interest rate percentage")
    has_interest = models.BooleanField(default=False)

    # Dates
    loan_date = models.DateField()
    due_date = models.DateField()

    # Status
    is_active = models.BooleanField(default=True)
    is_fully_repaid = models.BooleanField(default=False)
    repaid_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['due_date', '-created_at']

    @property
    def total_repaid(self):
        return self.repayments.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    @property
    def remaining_balance(self):
        return max(self.current_balance - self.total_repaid, Decimal('0'))

    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and not self.is_fully_repaid

    def receive_repayment(self, amount, account, notes=""):
        """Receive a repayment for this loan"""
        if amount <= 0:
            raise ValueError("Repayment amount must be positive")

        repayment = LoanRepayment.objects.create(
            loan=self,
            amount=amount,
            account=account,
            notes=notes
        )

        # Check if loan is fully repaid
        if self.remaining_balance <= 0:
            self.is_fully_repaid = True
            self.repaid_date = timezone.now().date()
            self.is_active = False
            self.save()

        return repayment

    def __str__(self):
        return f"Loan to {self.borrower_name}: {self.remaining_balance}/{self.principal_amount}"


class DebtPayment(BaseModel):
    """
    Payment made towards a personal debt
    """
    debt = models.ForeignKey(PersonalDebt, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2,
                               validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateField(default=timezone.now)
    account = models.ForeignKey(Account, on_delete=models.CASCADE,
                              limit_choices_to={'scope': FinanceScope.PERSONAL})
    notes = models.TextField(blank=True)

    # Linked transaction (automatically created)
    transaction = models.OneToOneField(PersonalTransaction, on_delete=models.CASCADE,
                                     null=True, blank=True, related_name='debt_payment')

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            # Create corresponding expense transaction
            self.transaction = PersonalTransaction.objects.create(
                user=self.debt.user,
                type=TransactionType.EXPENSE,
                amount=self.amount,
                account=self.account,
                expense_category=PersonalExpenseCategory.DEBT,
                description=f"Debt payment to {self.debt.creditor_name}",
                reason=f"Payment for debt: {self.debt.description}",
                date=timezone.now(),
                notes=self.notes
            )
            self.save(update_fields=['transaction'])

    def __str__(self):
        return f"Payment: {self.amount} to {self.debt.creditor_name}"


class LoanRepayment(BaseModel):
    """
    Repayment received for a personal loan
    """
    loan = models.ForeignKey(PersonalLoan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=12, decimal_places=2,
                               validators=[MinValueValidator(Decimal('0.01'))])
    repayment_date = models.DateField(default=timezone.now)
    account = models.ForeignKey(Account, on_delete=models.CASCADE,
                              limit_choices_to={'scope': FinanceScope.PERSONAL})
    notes = models.TextField(blank=True)

    # Linked transaction (automatically created)
    transaction = models.OneToOneField(PersonalTransaction, on_delete=models.CASCADE,
                                     null=True, blank=True, related_name='loan_repayment')

    class Meta:
        ordering = ['-repayment_date']

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            # Create corresponding income transaction
            self.transaction = PersonalTransaction.objects.create(
                user=self.loan.user,
                type=TransactionType.INCOME,
                amount=self.amount,
                account=self.account,
                income_source=PersonalIncomeSource.LOAN_REPAYMENT,
                description=f"Loan repayment from {self.loan.borrower_name}",
                reason=f"Repayment for loan: {self.loan.description}",
                date=timezone.now(),
                notes=self.notes
            )
            self.save(update_fields=['transaction'])

    def __str__(self):
        return f"Repayment: {self.amount} from {self.loan.borrower_name}"
