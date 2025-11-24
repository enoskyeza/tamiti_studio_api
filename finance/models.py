from datetime import datetime, time

from django.db import models
from django.utils import timezone
from core.models import BaseModel
from users.models import User
from common.enums import (
    PartyType, InvoiceDirection, TransactionType, AccountType, Currency,
    PriorityLevel, PaymentCategory, QuotationStatus, PaymentMethod,
    FinanceScope, PersonalExpenseCategory, PersonalIncomeSource, BudgetPeriod
)
from django.db.models import Sum, F, DecimalField, Value as V, Q
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
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
    domain = models.CharField(
        max_length=20,
        choices=(
            ("studio", "Studio"),
            ("sacco", "Sacco"),
        ),
        default="studio",
    )
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
    
    # New fields for enhanced functionality
    has_items = models.BooleanField(default=False, help_text="True if requisition uses itemized breakdown")
    calculated_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Auto-calculated from items")

    def approve(self, user: User):
        self.approved_by = user
        self.status = 'approved'
        self.date_approved = timezone.now().date()
        self.save()

    def reject(self, user: User):
        """Mark this requisition as rejected."""
        # For now we only track final status; approval fields are only meaningful for approved requisitions
        self.status = 'rejected'
        self.approved_by = None
        self.date_approved = None
        self.save(update_fields=['status', 'approved_by', 'date_approved'])
    
    def update_total(self):
        """Update calculated_total from items"""
        if self.has_items:
            from django.db.models import Sum
            total = self.items.aggregate(total=Sum('amount'))['total'] or 0
            self.calculated_total = total
            # Update main amount if using items
            self.amount = total
            self.save(update_fields=['calculated_total', 'amount'])
    
    @property
    def effective_total(self):
        """Return calculated total if has items, otherwise manual amount"""
        return self.calculated_total if self.has_items else self.amount
    
    @property
    def document_count(self):
        return self.documents.count()
    
    @property
    def comment_count(self):
        from django.contrib.contenttypes.models import ContentType
        from comments.models import Comment
        ct = ContentType.objects.get_for_model(self)
        return Comment.objects.filter(content_type=ct, object_id=self.id).count()
    
    def can_approve(self, user):
        """Check if user can approve this requisition"""
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        # Allow authenticated admin/staff users to approve, even if they created it
        if not user or not getattr(user, 'is_authenticated', False):
            return False

        if getattr(user, 'is_staff', False):
            return True

        permission_service = PermissionService()
        return permission_service.has_permission(
            user=user,
            action='approve',
            content_type=ContentType.objects.get_for_model(Requisition),
            obj=self,
            use_cache=True,
            log_check=False
        )

    def can_edit(self, user):
        """Check if user can edit this requisition"""
        return self.requested_by == user or user.is_staff

    def can_delete(self, user):
        """Check if user can delete this requisition"""
        return self.requested_by == user and self.status == 'pending'


class RequisitionDocument(BaseModel):
    """Supporting documents for requisitions"""
    requisition = models.ForeignKey(Requisition, related_name='documents', on_delete=models.CASCADE)
    file = models.FileField(upload_to='requisitions/documents/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.filename} - {self.requisition.purpose[:50]}"


class RequisitionItem(BaseModel):
    """Individual items/particulars for requisitions"""
    requisition = models.ForeignKey(Requisition, related_name='items', on_delete=models.CASCADE)
    particular = models.CharField(max_length=255, help_text="Item description")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    class Meta:
        ordering = ['id']
    
    def save(self, *args, **kwargs):
        # Calculate amount from quantity and unit cost
        self.amount = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
        # Update requisition total after saving
        self.requisition.update_total()
    
    def delete(self, *args, **kwargs):
        requisition = self.requisition
        super().delete(*args, **kwargs)
        # Update requisition total after deletion
        requisition.update_total()
    
    def __str__(self):
        return f"{self.particular} - {self.quantity} x {self.unit_cost}"


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
    transaction_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Fees/charges associated with this transaction",
    )
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
            # For company transactions, apply net cash effect including charges
            total_amount = self.amount
            if self.type == TransactionType.INCOME:
                # Net cash in = amount - charge
                total_amount = self.amount - (self.transaction_charge or 0)
            else:
                # Net cash out = amount + charge
                total_amount = self.amount + (self.transaction_charge or 0)

            self.account.apply_transaction(self.type, total_amount)


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

    class Meta:
        ordering = ('-date', '-created_at')

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

    # Linkages
    linked_invoice = models.ForeignKey(
        'finance.Invoice', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='personal_transactions'
    )
    linked_goal = models.ForeignKey(
        'finance.PersonalSavingsGoal', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transactions'
    )
    linked_budget = models.ForeignKey(
        'finance.PersonalBudget', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='transactions'
    )
    invoice_payment = models.OneToOneField(
        'finance.Payment', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='personal_transaction'
    )

    GOAL_DIRECTION_CHOICES = (
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
    )
    goal_applied_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0')
    )
    goal_applied_direction = models.CharField(
        max_length=10, choices=GOAL_DIRECTION_CHOICES, blank=True, default=''
    )

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
    affects_profit = models.BooleanField(
        default=True,
        help_text="If false, exclude from income/expense reporting while still impacting cash balances"
    )

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
            total_amount = self.amount + (self.transaction_charge or 0)

            if self.type == TransactionType.INCOME:
                self.account.balance += self.amount - (self.transaction_charge or 0)
            elif self.type == TransactionType.EXPENSE:
                self.account.balance -= total_amount

            self.account.save(update_fields=['balance'])

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
        """Recalculate spent amount from transactions, including direct links"""
        transactions = PersonalTransaction.objects.filter(
            user=self.user,
            type=TransactionType.EXPENSE,
            date__range=[self.start_date, self.end_date]
        )

        total = transactions.filter(
            Q(expense_category=self.category) | Q(linked_budget=self)
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

    def add_contribution(self, amount, description="Manual contribution", create_transaction=True, transaction=None):
        """Add a contribution to this savings goal"""
        self.current_amount += amount
        if self.current_amount >= self.target_amount and not self.is_achieved:
            self.is_achieved = True
            self.achieved_date = timezone.now().date()
        if self.current_amount < self.target_amount and self.is_achieved:
            self.is_achieved = False
            self.achieved_date = None
        self.save()

        if create_transaction:
            account = self.user.account_set.filter(scope=FinanceScope.PERSONAL).first()
            if not account:
                raise ValidationError({'account': 'Create at least one personal account before adding contributions.'})
            PersonalTransaction.objects.create(
                user=self.user,
                type=TransactionType.EXPENSE,
                amount=amount,
                account=account,
                expense_category=PersonalExpenseCategory.SAVINGS,
                description=f"Savings for: {self.name}",
                reason=description,
                linked_goal=self,
                goal_applied_amount=amount,
                goal_applied_direction='deposit',
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
    received_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Amount credited to the destination account after applying exchange rate"
    )

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

    def save(self, *args, **kwargs):
        if not self.received_amount:
            calculated = (self.amount or Decimal('0')) * (self.exchange_rate or Decimal('1'))
            self.received_amount = calculated.quantize(Decimal('0.01')) if calculated else Decimal('0')
        super().save(*args, **kwargs)

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
        return self.payments.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')

    @property
    def remaining_balance(self):
        return max(self.current_balance - self.total_paid, Decimal('0'))

    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and not self.is_fully_paid

    def make_payment(self, amount, account, notes="", interest_amount=Decimal('0')):
        """Make a payment towards this debt"""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        if interest_amount < 0:
            raise ValueError("Interest amount cannot be negative")

        principal_amount = Decimal(str(amount)) - Decimal(str(interest_amount))
        if principal_amount < 0:
            raise ValueError("Interest amount cannot exceed payment amount")

        if principal_amount > self.remaining_balance:
            raise ValueError("Principal component cannot exceed the remaining balance")

        payment = DebtPayment.objects.create(
            debt=self,
            amount=amount,
            account=account,
            notes=notes,
            principal_amount=principal_amount,
            interest_amount=Decimal(str(interest_amount))
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
        return self.repayments.aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')

    @property
    def remaining_balance(self):
        return max(self.current_balance - self.total_repaid, Decimal('0'))

    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and not self.is_fully_repaid

    def receive_repayment(self, amount, account, notes="", interest_amount=Decimal('0')):
        """Receive a repayment for this loan"""
        if amount <= 0:
            raise ValueError("Repayment amount must be positive")
        if interest_amount < 0:
            raise ValueError("Interest amount cannot be negative")

        principal_amount = Decimal(str(amount)) - Decimal(str(interest_amount))
        if principal_amount < 0:
            raise ValueError("Interest amount cannot exceed repayment amount")

        if principal_amount > self.remaining_balance:
            raise ValueError("Principal component cannot exceed the outstanding loan balance")

        repayment = LoanRepayment.objects.create(
            loan=self,
            amount=amount,
            account=account,
            notes=notes,
            principal_amount=principal_amount,
            interest_amount=Decimal(str(interest_amount))
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
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Portion of the payment applied to principal"
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Portion of the payment applied to interest"
    )

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        interest = self.interest_amount or Decimal('0')
        principal = self.principal_amount or Decimal('0')

        if principal == 0:
            principal = self.amount - interest

        if principal < 0:
            raise ValidationError("Interest amount cannot exceed total payment")

        total_components = (principal + interest).quantize(Decimal('0.01'))
        if total_components != self.amount.quantize(Decimal('0.01')):
            raise ValidationError("Principal and interest must sum to the total payment amount")

        self.principal_amount = principal
        self.interest_amount = interest

        super().save(*args, **kwargs)

        if is_new:
            payment_dt = datetime.combine(self.payment_date, time.min)
            if timezone.is_naive(payment_dt):
                payment_dt = timezone.make_aware(payment_dt)

            principal_tx = None
            if principal > 0:
                principal_tx = PersonalTransaction.objects.create(
                    user=self.debt.user,
                    type=TransactionType.EXPENSE,
                    amount=principal,
                    account=self.account,
                    expense_category=PersonalExpenseCategory.DEBT,
                    description=f"Debt payment to {self.debt.creditor_name}",
                    reason=f"Payment for debt: {self.debt.description}",
                    date=payment_dt,
                    notes=self.notes,
                    affects_profit=False,
                )

            if interest > 0:
                PersonalTransaction.objects.create(
                    user=self.debt.user,
                    type=TransactionType.EXPENSE,
                    amount=interest,
                    account=self.account,
                    expense_category=PersonalExpenseCategory.DEBT_INTEREST,
                    description=f"Debt interest payment to {self.debt.creditor_name}",
                    reason=f"Interest for debt: {self.debt.description}",
                    date=payment_dt,
                    notes=self.notes,
                    affects_profit=True,
                )

            if principal_tx:
                self.transaction = principal_tx
                super().save(update_fields=['transaction'])

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
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Portion of the repayment applied to principal"
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Portion of the repayment recognised as interest"
    )

    class Meta:
        ordering = ['-repayment_date']

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        interest = self.interest_amount or Decimal('0')
        principal = self.principal_amount or Decimal('0')

        if principal == 0:
            principal = self.amount - interest

        if principal < 0:
            raise ValidationError("Interest amount cannot exceed total repayment")

        total_components = (principal + interest).quantize(Decimal('0.01'))
        if total_components != self.amount.quantize(Decimal('0.01')):
            raise ValidationError("Principal and interest must sum to the total repayment amount")

        self.principal_amount = principal
        self.interest_amount = interest

        super().save(*args, **kwargs)

        if is_new:
            repayment_dt = datetime.combine(self.repayment_date, time.min)
            if timezone.is_naive(repayment_dt):
                repayment_dt = timezone.make_aware(repayment_dt)

            principal_tx = None
            if principal > 0:
                principal_tx = PersonalTransaction.objects.create(
                    user=self.loan.user,
                    type=TransactionType.INCOME,
                    amount=principal,
                    account=self.account,
                    income_source=PersonalIncomeSource.LOAN_REPAYMENT,
                    description=f"Loan principal from {self.loan.borrower_name}",
                    reason=f"Principal repayment for loan: {self.loan.description}",
                    date=repayment_dt,
                    notes=self.notes,
                    affects_profit=False,
                )

            if interest > 0:
                PersonalTransaction.objects.create(
                    user=self.loan.user,
                    type=TransactionType.INCOME,
                    amount=interest,
                    account=self.account,
                    income_source=PersonalIncomeSource.LOAN_INTEREST,
                    description=f"Loan interest from {self.loan.borrower_name}",
                    reason=f"Interest repayment for loan: {self.loan.description}",
                    date=repayment_dt,
                    notes=self.notes,
                    affects_profit=True,
                )

            if principal_tx:
                self.transaction = principal_tx
                super().save(update_fields=['transaction'])

    def __str__(self):
        return f"Repayment: {self.amount} from {self.loan.borrower_name}"


# COMPANY FINANCE MODELS

class CompanyBudget(BaseModel):
    """
    Budget management for company expense categories
    """
    name = models.CharField(max_length=100, help_text="Budget name/title")
    department = models.ForeignKey('accounts.Department', on_delete=models.CASCADE, 
                                 related_name='budgets', null=True, blank=True)
    category = models.CharField(max_length=50, choices=PersonalExpenseCategory.choices)
    period = models.CharField(max_length=20, choices=BudgetPeriod.choices, default=BudgetPeriod.MONTHLY)

    # Budget amounts
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])
    spent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     validators=[MinValueValidator(Decimal('0'))])

    # Period tracking
    start_date = models.DateField()
    end_date = models.DateField()

    # Settings
    is_active = models.BooleanField(default=True)
    alert_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80,
                                        help_text="Alert when spent percentage reaches this threshold")
    
    # Approval workflow
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='approved_company_budgets')
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['department', 'category', 'start_date']
        ordering = ['-start_date', 'category']

    @property
    def spent_percentage(self):
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0

    @property
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    @property
    def is_over_budget(self):
        return self.spent_amount > self.allocated_amount

    @property
    def is_near_limit(self):
        return self.spent_percentage >= self.alert_threshold

    def __str__(self):
        dept_name = self.department.name if self.department else "Company"
        return f"{dept_name} - {self.name} ({self.get_period_display()})"


class CompanySavingsGoal(BaseModel):
    """
    Company savings goals and targets
    """
    name = models.CharField(max_length=100, help_text="Savings goal name")
    description = models.TextField(blank=True, help_text="Goal description and purpose")
    department = models.ForeignKey('accounts.Department', on_delete=models.CASCADE,
                                 related_name='savings_goals', null=True, blank=True)
    
    # Goal amounts
    target_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                      validators=[MinValueValidator(Decimal('0.01'))])
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       validators=[MinValueValidator(Decimal('0'))])
    
    # Timeline
    start_date = models.DateField()
    target_date = models.DateField()
    
    # Settings
    is_active = models.BooleanField(default=True)
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='medium')
    
    # Linked account for savings
    savings_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='company_savings_goals')

    class Meta:
        ordering = ['-priority', '-target_date']

    @property
    def progress_percentage(self):
        if self.target_amount > 0:
            return min((self.current_amount / self.target_amount) * 100, 100)
        return 0

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.current_amount, 0)

    @property
    def is_completed(self):
        return self.current_amount >= self.target_amount

    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.target_date:
            delta = self.target_date - timezone.now().date()
            return delta.days
        return None

    def __str__(self):
        dept_name = self.department.name if self.department else "Company"
        return f"{dept_name} - {self.name}"


class CompanyRecurringTransaction(BaseModel):
    """
    Recurring transactions for company operations (bills, subscriptions, etc.)
    """
    name = models.CharField(max_length=100, help_text="Transaction name/description")
    department = models.ForeignKey('accounts.Department', on_delete=models.CASCADE,
                                 related_name='recurring_transactions', null=True, blank=True)
    
    # Transaction details
    amount = models.DecimalField(max_digits=12, decimal_places=2,
                               validators=[MinValueValidator(Decimal('0.01'))])
    transaction_type = models.CharField(max_length=20, choices=[
        ('expense', 'Expense'),
        ('income', 'Income'),
    ], default='expense')
    
    category = models.CharField(max_length=50, choices=PersonalExpenseCategory.choices)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='company_recurring_transactions')
    
    # Recurrence settings
    frequency = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], default='monthly')
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for indefinite")
    next_due_date = models.DateField()
    
    # Settings
    is_active = models.BooleanField(default=True)
    auto_create = models.BooleanField(default=False, 
                                    help_text="Automatically create transactions when due")
    
    # Approval workflow
    requires_approval = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='approved_recurring_transactions')
    
    # Tracking
    last_created_date = models.DateField(null=True, blank=True)
    total_created = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['next_due_date', 'name']

    @property
    def is_due(self):
        from django.utils import timezone
        return self.next_due_date <= timezone.now().date()

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.next_due_date < timezone.now().date()

    def calculate_next_due_date(self):
        """Calculate the next due date based on frequency"""
        from dateutil.relativedelta import relativedelta
        
        if self.frequency == 'daily':
            return self.next_due_date + timedelta(days=1)
        elif self.frequency == 'weekly':
            return self.next_due_date + timedelta(weeks=1)
        elif self.frequency == 'monthly':
            return self.next_due_date + relativedelta(months=1)
        elif self.frequency == 'quarterly':
            return self.next_due_date + relativedelta(months=3)
        elif self.frequency == 'yearly':
            return self.next_due_date + relativedelta(years=1)
        return self.next_due_date

    def create_transaction(self):
        """Create a transaction from this recurring template"""
        if self.transaction_type == 'expense':
            transaction = Transaction.objects.create(
                account=self.account,
                amount=self.amount,
                expense_category=self.category,
                description=f"Recurring: {self.name}",
                date=self.next_due_date,
                notes=f"Auto-generated from recurring transaction: {self.name}"
            )
        else:
            transaction = PersonalIncome.objects.create(
                account=self.account,
                amount=self.amount,
                income_source='OTHER',
                description=f"Recurring: {self.name}",
                date=self.next_due_date,
                notes=f"Auto-generated from recurring transaction: {self.name}"
            )
        
        # Update tracking
        self.last_created_date = self.next_due_date
        self.next_due_date = self.calculate_next_due_date()
        self.total_created += 1
        self.save(update_fields=['last_created_date', 'next_due_date', 'total_created'])
        
        return transaction

    def __str__(self):
        dept_name = self.department.name if self.department else "Company"
        return f"{dept_name} - {self.name} ({self.get_frequency_display()})"
