from django.db import models
from django.utils import timezone
from core.models import BaseModel
from users.models import User
from common.enums import PartyType, InvoiceDirection, TransactionType, AccountType, Currency, PriorityLevel, PaymentCategory
from django.db.models import Sum


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

    def apply_transaction(self, tx_type, amount):
        if tx_type == 'income':
            self.balance += amount
        else:
            self.balance -= amount
        self.save(update_fields=['balance'])


class Invoice(BaseModel):
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    direction = models.CharField(max_length=10, choices=InvoiceDirection.choices)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    issued_date = models.DateField()
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    related_file = models.FileField(upload_to='invoices/', blank=True, null=True)

    def __str__(self):
        return f"Invoice #{self.id} - {self.party.name}"

    @property
    def balance(self):
        paid = self.payments.aggregate(total=Sum('amount'))['total'] or 0
        return self.total_amount - paid

    def check_paid_status(self):
        if self.balance <= 0:
            self.is_paid = True
            self.save(update_fields=['is_paid'])


class Goal(BaseModel):
    title = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

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
    transaction = models.OneToOneField(
        'Transaction', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_payment'
    )
    receipt_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    notes = models.TextField(blank=True)
    goal = models.ForeignKey(Goal, null=True, blank=True, related_name='payments', on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        creating = self._state.adding
        super().save(*args, **kwargs)

        if creating and not self.transaction:
            tx_type = 'income' if self.direction == 'incoming' else 'expense'

            tx = Transaction.objects.create(
                type=tx_type,
                amount=self.amount,
                description=self.notes or f"{tx_type.capitalize()} payment by {self.party}",
                account=self.account,
                related_invoice=self.invoice,
                related_requisition=self.requisition,
                related_payment=self,
                date=self.created_at,
                is_automated=True,
            )
            self.transaction = tx
            super().save(update_fields=['transaction'])

        if self.invoice:
            self.invoice.check_paid_status()
        if self.goal:
            self.goal.update_progress()



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

