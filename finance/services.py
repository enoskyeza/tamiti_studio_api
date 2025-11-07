from datetime import date as date_cls, datetime as datetime_cls
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db import models

from finance.models import Payment, Transaction, Invoice
from common.enums import TransactionType, PaymentMethod, InvoiceDirection, PaymentCategory

LINK_UNSET = object()


class FinanceService:
    @staticmethod
    @db_transaction.atomic
    def record_invoice_payment(*, invoice: Invoice, amount, account=None, method=None, date=None, notes: str = '', created_by=None) -> Payment:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero'})
        if amount > invoice.amount_due:
            raise ValidationError({'amount': 'Payment exceeds amount due'})

        # Payment direction follows cash flow: paying supplier (incoming invoice) is outgoing; collecting from customer (outgoing invoice) is incoming
        payment = Payment.objects.create(
            direction='outgoing' if invoice.direction == InvoiceDirection.INCOMING else 'incoming',
            amount=amount,
            party=invoice.party,
            invoice=invoice,
            account=account,
            notes=notes or '',
            method=method or PaymentMethod.CASH,
        )

        payment_date = timezone.localdate()
        if date is not None:
            if isinstance(date, datetime_cls):
                payment_date = date.date()
            elif isinstance(date, date_cls):
                payment_date = date
            elif isinstance(date, str):
                try:
                    payment_date = datetime_cls.fromisoformat(date).date()
                except ValueError:
                    payment_date = timezone.localdate()

        invoice_reference = invoice.number or f"#{invoice.id}"
        payment_description = notes or f"Payment for invoice {invoice_reference}"

        # Map invoice direction to transaction type
        # Paying INCOMING invoice => EXPENSE; Paying OUTGOING invoice => INCOME
        tx_type = TransactionType.EXPENSE if invoice.direction == InvoiceDirection.INCOMING else TransactionType.INCOME
        tx = Transaction.objects.create(
            type=tx_type,
            amount=amount,
            description=payment_description,
            account=account,
            category=PaymentCategory.INVOICE,
            related_invoice=invoice,
            related_payment=payment,
            date=payment_date,
            is_automated=True,
        )
        payment.transaction = tx
        payment.save(update_fields=['transaction'])
        return payment


class PersonalFinanceService:
    """Service class for personal finance business logic and operations"""

    @staticmethod
    def create_personal_transaction(user, transaction_data):
        """
        Create a personal transaction with proper validation and balance updates
        """
        from finance.models import PersonalTransaction, Account
        from common.enums import FinanceScope, TransactionType
        from decimal import Decimal

        account_value = transaction_data.get('account')
        if isinstance(account_value, Account):
            account = account_value
        else:
            account = Account.objects.get(
                id=account_value,
                scope=FinanceScope.PERSONAL,
                owner=user
            )

        # Create transaction
        transaction_data = transaction_data.copy()
        transaction_data.pop('account', None)
        invoice_obj = transaction_data.pop('linked_invoice', None)
        goal_obj = transaction_data.pop('linked_goal', None)
        budget_obj = transaction_data.pop('linked_budget', None)

        transaction = PersonalTransaction.objects.create(
            user=user,
            type=transaction_data['type'],
            amount=Decimal(str(transaction_data['amount'])),
            account=account,
            description=transaction_data['description'],
            transaction_charge=Decimal(str(transaction_data.get('transaction_charge', 0))),
            income_source=transaction_data.get('income_source', ''),
            expense_category=transaction_data.get('expense_category', ''),
            reason=transaction_data['reason'],
            date=transaction_data.get('date', timezone.now()),
            reference_number=transaction_data.get('reference_number', ''),
            receipt_image=transaction_data.get('receipt_image'),
            tags=transaction_data.get('tags', []),
            location=transaction_data.get('location', ''),
            notes=transaction_data.get('notes', ''),
            linked_invoice=invoice_obj,
            linked_goal=goal_obj,
            linked_budget=budget_obj,
        )

        # Update account balance
        PersonalFinanceService.update_account_balance(account, transaction)

        # Apply linked entities (invoice, goal, budget)
        PersonalFinanceService.apply_transaction_linkages(
            transaction,
            linked_invoice=invoice_obj,
            linked_goal=goal_obj,
            linked_budget=budget_obj,
        )

        # Update related budgets based on category linkage
        PersonalFinanceService.update_budget_spending(user, transaction)

        return transaction

    @staticmethod
    def update_account_balance(account, transaction):
        """Update account balance based on transaction type"""
        from common.enums import TransactionType

        total_amount = transaction.amount + transaction.transaction_charge

        if transaction.type == TransactionType.INCOME:
            account.balance += transaction.amount - transaction.transaction_charge
        elif transaction.type == TransactionType.EXPENSE:
            account.balance -= total_amount

        account.save(update_fields=['balance'])

    @staticmethod
    def update_budget_spending(user, transaction):
        """Update budget spending when expense transaction is created"""
        from finance.models import PersonalBudget
        from common.enums import TransactionType
        from django.utils import timezone

        if transaction.type != TransactionType.EXPENSE or not transaction.expense_category:
            return

        # Find active budgets for this category
        current_date = timezone.now().date()
        budgets = PersonalBudget.objects.filter(
            user=user,
            category=transaction.expense_category,
            is_active=True,
            start_date__lte=current_date,
            end_date__gte=current_date
        )

        # Update spent amounts (this will trigger the property calculations)
        for budget in budgets:
            budget.update_spent_amount()

    @staticmethod
    @db_transaction.atomic
    def update_personal_transaction(transaction, data):
        """Update transaction metadata and re-sync linked entities"""
        update_fields = []

        simple_fields = [
            'description', 'transaction_charge', 'reason', 'reference_number',
            'receipt_image', 'tags', 'location', 'notes'
        ]

        for field in simple_fields:
            if field in data:
                setattr(transaction, field, data[field])
                update_fields.append(field)

        if update_fields:
            update_fields.append('updated_at')
            transaction.save(update_fields=update_fields)

        PersonalFinanceService.apply_transaction_linkages(
            transaction,
            linked_invoice=data.get('linked_invoice', LINK_UNSET),
            linked_goal=data.get('linked_goal', LINK_UNSET),
            linked_budget=data.get('linked_budget', LINK_UNSET),
        )

        PersonalFinanceService.update_budget_spending(transaction.user, transaction)

        return transaction

    @staticmethod
    @db_transaction.atomic
    def apply_transaction_linkages(transaction, linked_invoice=LINK_UNSET, linked_goal=LINK_UNSET, linked_budget=LINK_UNSET):
        """Synchronize invoice, goal, and budget associations for a transaction"""
        PersonalFinanceService._handle_invoice_link(transaction, linked_invoice)
        PersonalFinanceService._handle_goal_link(transaction, linked_goal)
        PersonalFinanceService._handle_budget_link(transaction, linked_budget)

    @staticmethod
    def _handle_invoice_link(transaction, new_invoice):
        from common.enums import InvoiceDirection

        target_invoice = transaction.linked_invoice if new_invoice is LINK_UNSET else new_invoice
        payment = transaction.invoice_payment

        if new_invoice is not LINK_UNSET and target_invoice != transaction.linked_invoice:
            if payment:
                payment.delete()
                payment = None
            transaction.linked_invoice = target_invoice
            transaction.invoice_payment = None
            transaction.save(update_fields=['linked_invoice', 'invoice_payment', 'updated_at'])

        if target_invoice is None:
            if payment:
                payment.delete()
                transaction.invoice_payment = None
                transaction.save(update_fields=['invoice_payment', 'updated_at'])
            return

        applied_amount = transaction.amount
        if applied_amount <= 0:
            return

        if target_invoice.direction == InvoiceDirection.INCOMING and transaction.type != TransactionType.EXPENSE:
            raise ValidationError({'linked_invoice': 'Paying an incoming invoice requires an expense transaction.'})
        if target_invoice.direction == InvoiceDirection.OUTGOING and transaction.type != TransactionType.INCOME:
            raise ValidationError({'linked_invoice': 'Receiving payment for an outgoing invoice requires an income transaction.'})

        amount_due = target_invoice.amount_due
        if applied_amount > amount_due + Decimal('0.01'):
            raise ValidationError({'linked_invoice': 'Applied amount exceeds the outstanding invoice balance.'})

        payment_direction = 'outgoing' if target_invoice.direction == InvoiceDirection.INCOMING else 'incoming'

        if payment:
            payment.amount = applied_amount
            payment.direction = payment_direction
            payment.account = transaction.account
            payment.invoice = target_invoice
            payment.notes = f"Linked from personal transaction #{transaction.id}"
            payment.save()
        else:
            payment = Payment.objects.create(
                direction=payment_direction,
                amount=applied_amount,
                party=target_invoice.party,
                invoice=target_invoice,
                account=transaction.account,
                method=PaymentMethod.CASH,
                notes=f"Linked from personal transaction #{transaction.id}"
            )
            transaction.invoice_payment = payment
            transaction.save(update_fields=['invoice_payment', 'updated_at'])

    @staticmethod
    def _handle_goal_link(transaction, new_goal):
        from finance.models import PersonalSavingsGoal

        target_goal = transaction.linked_goal if new_goal is LINK_UNSET else new_goal
        previous_goal = transaction.linked_goal
        previous_amount = transaction.goal_applied_amount or Decimal('0')
        previous_direction = transaction.goal_applied_direction

        # Reverse previous contribution if goal changed or removed
        if previous_goal and previous_amount > 0:
            PersonalFinanceService._adjust_goal_balance(
                previous_goal,
                previous_amount,
                previous_direction,
                reverse=True
            )
            transaction.goal_applied_amount = Decimal('0')
            transaction.goal_applied_direction = ''
            if target_goal != previous_goal:
                transaction.linked_goal = None
            transaction.save(update_fields=['goal_applied_amount', 'goal_applied_direction', 'linked_goal', 'updated_at'])

        if not target_goal:
            return

        if not isinstance(target_goal, PersonalSavingsGoal):
            target_goal = PersonalSavingsGoal.objects.get(id=target_goal)

        if target_goal.user != transaction.user:
            raise ValidationError({'linked_goal': 'Goal must belong to the current user.'})

        if transaction.type == TransactionType.INCOME:
            applied_amount = (transaction.amount - transaction.transaction_charge).quantize(Decimal('0.01'))
            direction = 'deposit'
        else:
            applied_amount = (transaction.amount + transaction.transaction_charge).quantize(Decimal('0.01'))
            direction = 'withdraw'

        if applied_amount <= 0:
            return

        PersonalFinanceService._adjust_goal_balance(target_goal, applied_amount, direction)

        transaction.goal_applied_amount = applied_amount
        transaction.goal_applied_direction = direction
        transaction.linked_goal = target_goal
        transaction.save(update_fields=['goal_applied_amount', 'goal_applied_direction', 'linked_goal', 'updated_at'])

    @staticmethod
    def _adjust_goal_balance(goal, amount, direction, reverse=False):
        if amount <= 0:
            return

        delta = amount if direction == 'deposit' else -amount
        if reverse:
            delta = -delta

        goal.current_amount = max(goal.current_amount + delta, Decimal('0'))

        if goal.current_amount >= goal.target_amount:
            if not goal.is_achieved:
                goal.is_achieved = True
                goal.achieved_date = timezone.now().date()
        else:
            goal.is_achieved = False
            goal.achieved_date = None

        goal.save(update_fields=['current_amount', 'is_achieved', 'achieved_date'])

    @staticmethod
    def _handle_budget_link(transaction, new_budget):
        from finance.models import PersonalBudget

        previous_budget = transaction.linked_budget
        target_budget = previous_budget if new_budget is LINK_UNSET else new_budget

        if new_budget is not LINK_UNSET and target_budget != previous_budget:
            if target_budget and not isinstance(target_budget, PersonalBudget):
                target_budget = PersonalBudget.objects.get(id=target_budget)
            if target_budget and target_budget.user != transaction.user:
                raise ValidationError({'linked_budget': 'Budget must belong to the current user.'})
            transaction.linked_budget = target_budget
            transaction.save(update_fields=['linked_budget', 'updated_at'])

        if previous_budget and previous_budget != target_budget:
            previous_budget.update_spent_amount()

        if target_budget:
            target_budget.update_spent_amount()

    @staticmethod
    def get_monthly_summary(user, year, month):
        """Generate comprehensive monthly financial summary"""
        from finance.models import PersonalTransaction
        from common.enums import TransactionType, PersonalExpenseCategory, PersonalIncomeSource
        from django.db.models import Sum, Count
        from decimal import Decimal
        import calendar

        # Get date range for the month
        start_date = timezone.datetime(year, month, 1).date()
        if month == 12:
            end_date = timezone.datetime(year + 1, 1, 1).date()
        else:
            end_date = timezone.datetime(year, month + 1, 1).date()

        # Get transactions for the month
        transactions = PersonalTransaction.objects.filter(
            user=user,
            date__gte=start_date,
            date__lt=end_date
        )

        # Calculate totals
        income_transactions = transactions.filter(type=TransactionType.INCOME, affects_profit=True)
        expense_transactions = transactions.filter(type=TransactionType.EXPENSE, affects_profit=True)

        total_income = income_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        total_expenses = expense_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        total_transaction_charges = transactions.aggregate(
            total=Sum('transaction_charge')
        )['total'] or Decimal('0')

        # Income by source
        income_by_source = {}
        for source in PersonalIncomeSource.choices:
            source_total = income_transactions.filter(
                income_source=source[0]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            if source_total > 0:
                income_by_source[source[1]] = source_total

        # Expenses by category
        expenses_by_category = {}
        for category in PersonalExpenseCategory.choices:
            category_total = expense_transactions.filter(
                expense_category=category[0]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            if category_total > 0:
                expenses_by_category[category[1]] = category_total

        return {
            'year': year,
            'month': month,
            'month_name': calendar.month_name[month],
            'total_income': total_income,
            'total_expenses': total_expenses,
            'total_transaction_charges': total_transaction_charges,
            'net_amount': total_income - total_expenses - total_transaction_charges,
            'transaction_count': transactions.count(),
            'income_transaction_count': income_transactions.count(),
            'expense_transaction_count': expense_transactions.count(),
            'income_by_source': income_by_source,
            'expenses_by_category': expenses_by_category,
            'average_transaction_amount': (
                (total_income + total_expenses) / transactions.count()
                if transactions.count() > 0 else Decimal('0')
            ),
        }

    @staticmethod
    def get_spending_insights(user, days=30):
        """Generate spending insights and analytics"""
        from finance.models import PersonalTransaction
        from common.enums import TransactionType, PersonalExpenseCategory
        from django.db.models import Sum, Count, Avg
        from decimal import Decimal
        from datetime import timedelta

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Get transactions for the period
        transactions = PersonalTransaction.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        )

        income_transactions = transactions.filter(type=TransactionType.INCOME, affects_profit=True)
        expense_transactions = transactions.filter(type=TransactionType.EXPENSE, affects_profit=True)

        total_income = income_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        total_expenses = expense_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        # Calculate daily averages
        average_daily_income = total_income / days if days > 0 else Decimal('0')
        average_daily_expense = total_expenses / days if days > 0 else Decimal('0')

        # Find highest expense day
        highest_expense_day = None
        daily_expenses = expense_transactions.values('date').annotate(
            daily_total=Sum('amount')
        ).order_by('-daily_total').first()

        if daily_expenses:
            highest_expense_day = {
                'date': daily_expenses['date'],
                'amount': daily_expenses['daily_total']
            }

        # Top expense categories
        top_categories = []
        for category in PersonalExpenseCategory.choices:
            category_total = expense_transactions.filter(
                expense_category=category[0]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            if category_total > 0:
                percentage = (category_total / total_expenses * 100) if total_expenses > 0 else 0
                top_categories.append({
                    'category': category[1],
                    'amount': category_total,
                    'percentage': round(float(percentage), 1)
                })

        top_categories.sort(key=lambda x: x['amount'], reverse=True)

        # Spending trend analysis (compare with previous period)
        previous_start = start_date - timedelta(days=days)
        previous_expenses = PersonalTransaction.objects.filter(
            user=user,
            type=TransactionType.EXPENSE,
            date__gte=previous_start,
            date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        if previous_expenses > 0:
            trend_percentage = ((total_expenses - previous_expenses) / previous_expenses) * 100
            if trend_percentage > 5:
                spending_trend = 'increasing'
            elif trend_percentage < -5:
                spending_trend = 'decreasing'
            else:
                spending_trend = 'stable'
        else:
            spending_trend = 'new'

        return {
            'period_days': days,
            'start_date': start_date,
            'end_date': end_date,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_amount': total_income - total_expenses,
            'average_daily_income': average_daily_income,
            'average_daily_expense': average_daily_expense,
            'highest_expense_day': highest_expense_day,
            'top_expense_categories': top_categories[:5],  # Top 5 categories
            'spending_trend': spending_trend,
            'transaction_count': transactions.count(),
            'expense_transaction_count': expense_transactions.count(),
        }

    @staticmethod
    def get_category_breakdown(user, days=30):
        """Get detailed expense breakdown by category"""
        from finance.models import PersonalTransaction
        from common.enums import TransactionType, PersonalExpenseCategory
        from django.db.models import Sum, Count, Avg
        from decimal import Decimal
        from datetime import timedelta

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        expense_transactions = PersonalTransaction.objects.filter(
            user=user,
            type=TransactionType.EXPENSE,
            date__gte=start_date,
            date__lte=end_date
        )

        total_expenses = expense_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        categories = []
        for category in PersonalExpenseCategory.choices:
            category_transactions = expense_transactions.filter(
                expense_category=category[0]
            )

            category_total = category_transactions.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')

            if category_total > 0:
                percentage = (category_total / total_expenses * 100) if total_expenses > 0 else 0
                avg_transaction = category_transactions.aggregate(
                    avg=Avg('amount')
                )['avg'] or Decimal('0')

                categories.append({
                    'category': category[0],
                    'category_display': category[1],
                    'total_amount': category_total,
                    'percentage': round(float(percentage), 1),
                    'transaction_count': category_transactions.count(),
                    'average_transaction': avg_transaction,
                })

        categories.sort(key=lambda x: x['total_amount'], reverse=True)

        return {
            'period_days': days,
            'start_date': start_date,
            'end_date': end_date,
            'total_expenses': total_expenses,
            'categories': categories,
        }

    @staticmethod
    def process_recurring_transactions():
        """Process due recurring transactions (to be run as scheduled task)"""
        from finance.models import PersonalTransactionRecurring, PersonalTransaction
        from django.utils import timezone

        now = timezone.now()
        today = now.date()

        # Get due recurring transactions
        due_recurring = PersonalTransactionRecurring.objects.filter(
            user=user,
            is_active=True,
            next_due_date__lte=today
        ).count()

        due_transactions = PersonalTransactionRecurring.objects.filter(
            user=user,
            is_active=True,
            next_due_date__lte=today
        )

        processed_count = 0
        for recurring in due_transactions:
            try:
                # Create the actual transaction
                transaction = PersonalTransaction.objects.create(
                    user=recurring.user,
                    type=recurring.type,
                    amount=recurring.amount,
                    account=recurring.account,
                    description=f"[Recurring] {recurring.description}",
                    transaction_charge=recurring.transaction_charge,
                    income_source=recurring.income_source if recurring.type == 'income' else '',
                    expense_category=recurring.expense_category if recurring.type == 'expense' else '',
                    reason=recurring.reason,
                    is_recurring=True,
                    recurring_parent=None,
                )

                # Update account balance
                PersonalFinanceService.update_account_balance(recurring.account, transaction)

                # Update budgets if expense
                PersonalFinanceService.update_budget_spending(recurring.user, transaction)

                # Update next execution date
                recurring.update_next_execution()

                processed_count += 1

            except Exception as e:
                # Log error but continue processing other transactions
                print(f"Error processing recurring transaction {recurring.id}: {str(e)}")
                continue

        return processed_count

    @staticmethod
    def create_budget_with_validation(user, budget_data):
        """Create a budget with proper validation"""
        from finance.models import PersonalBudget
        from decimal import Decimal

        # Validate date range
        start_date = budget_data['start_date']
        end_date = budget_data['end_date']

        if end_date <= start_date:
            raise ValueError("End date must be after start date")

        # Check for overlapping budgets in the same category
        overlapping_budgets = PersonalBudget.objects.filter(
            user=user,
            category=budget_data['category'],
            is_active=True
        ).filter(
            models.Q(start_date__lte=end_date) & models.Q(end_date__gte=start_date)
        )

        if overlapping_budgets.exists():
            raise ValueError(f"A budget for {budget_data['category']} already exists for this period")

        # Create budget
        budget = PersonalBudget.objects.create(
            user=user,
            name=budget_data['name'],
            category=budget_data['category'],
            allocated_amount=Decimal(str(budget_data['allocated_amount'])),
            period=budget_data['period'],
            start_date=start_date,
            end_date=end_date,
            description=budget_data.get('description', ''),
        )

        return budget

    @staticmethod
    def get_budget_alerts(user):
        """Get budget alerts for exceeded or nearly exceeded budgets"""
        from finance.models import PersonalBudget
        from django.utils import timezone

        current_date = timezone.now().date()
        active_budgets = PersonalBudget.objects.filter(
            user=user,
            is_active=True,
            start_date__lte=current_date,
            end_date__gte=current_date
        )

        alerts = []
        for budget in active_budgets:
            if budget.is_exceeded:
                alerts.append({
                    'type': 'exceeded',
                    'budget': budget,
                    'message': f"Budget '{budget.name}' has been exceeded by {budget.spent_amount - budget.allocated_amount}",
                    'severity': 'high'
                })
            elif budget.progress_percentage >= 80:
                alerts.append({
                    'type': 'warning',
                    'budget': budget,
                    'message': f"Budget '{budget.name}' is {budget.progress_percentage:.1f}% used",
                    'severity': 'medium'
                })

        return alerts

    @staticmethod
    def get_savings_goal_projections(user):
        """Calculate savings goal projections based on current saving rate"""
        from finance.models import PersonalSavingsGoal, PersonalTransaction
        from common.enums import TransactionType
        from django.db.models import Sum
        from decimal import Decimal
        from datetime import timedelta

        # Calculate recent savings rate (last 3 months)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)

        recent_income = PersonalTransaction.objects.filter(
            user=user,
            type=TransactionType.INCOME,
            date__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        recent_expenses = PersonalTransaction.objects.filter(
            user=user,
            type=TransactionType.EXPENSE,
            date__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        monthly_savings_rate = (recent_income - recent_expenses) / 3 if recent_income > recent_expenses else Decimal('0')

        # Get active savings goals
        active_goals = PersonalSavingsGoal.objects.filter(
            user=user,
            is_achieved=False
        )

        projections = []
        for goal in active_goals:
            if monthly_savings_rate > 0:
                months_to_complete = goal.remaining_amount / monthly_savings_rate
                projected_completion = end_date + timedelta(days=int(months_to_complete * 30))

                projections.append({
                    'goal': goal,
                    'monthly_savings_rate': monthly_savings_rate,
                    'months_to_complete': float(months_to_complete),
                    'projected_completion_date': projected_completion,
                    'on_track': projected_completion <= goal.target_date if goal.target_date else True
                })

        return projections

    @staticmethod
    @db_transaction.atomic
    def create_account_transfer(user, transfer_data):
        """
        Create an account transfer with automatic transaction creation
        """
        from finance.models import PersonalAccountTransfer, PersonalTransaction, Account
        from common.enums import FinanceScope, TransactionType, PersonalExpenseCategory, PersonalIncomeSource
        from decimal import Decimal

        # Validate accounts - handle both Account objects and IDs
        from_account_data = transfer_data['from_account']
        to_account_data = transfer_data['to_account']
        
        if isinstance(from_account_data, Account):
            from_account = from_account_data
        else:
            from_account = Account.objects.get(
                id=from_account_data,
                scope=FinanceScope.PERSONAL,
                owner=user
            )
            
        if isinstance(to_account_data, Account):
            to_account = to_account_data
        else:
            to_account = Account.objects.get(
                id=to_account_data,
                scope=FinanceScope.PERSONAL,
                owner=user
            )

        if from_account == to_account:
            raise ValidationError("Cannot transfer to the same account")

        amount = Decimal(str(transfer_data['amount'])).quantize(Decimal('0.01'))
        if amount <= 0:
            raise ValidationError({'amount': 'Transfer amount must be greater than zero'})

        transfer_fee = Decimal(str(transfer_data.get('transfer_fee', 0))).quantize(Decimal('0.01'))
        if transfer_fee < 0:
            raise ValidationError({'transfer_fee': 'Transfer fee cannot be negative'})

        exchange_rate = Decimal(str(transfer_data.get('exchange_rate', 1)))
        if exchange_rate <= 0:
            raise ValidationError({'exchange_rate': 'Exchange rate must be greater than zero'})

        received_amount = (amount * exchange_rate).quantize(Decimal('0.01'))
        total_debit = amount + transfer_fee

        if from_account.balance < total_debit:
            raise ValidationError({'amount': 'Insufficient funds to complete transfer including fees'})

        # Create the transfer record
        transfer = PersonalAccountTransfer.objects.create(
            user=user,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            received_amount=received_amount,
            transfer_fee=transfer_fee,
            exchange_rate=exchange_rate,
            description=transfer_data['description'],
            reference_number=transfer_data.get('reference_number', ''),
            date=transfer_data.get('date', timezone.now())
        )

        # Create debit transaction (amount + fee from source account)
        debit_transaction = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.EXPENSE,
            amount=amount,
            account=from_account,
            expense_category=PersonalExpenseCategory.TRANSFER,
            description=f"Transfer to {to_account.name}",
            reason=transfer_data['description'],
            date=transfer.date,
            reference_number=transfer.reference_number,
            affects_profit=False,
        )

        # Create credit transaction (amount to destination account)
        credit_transaction = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.INCOME,
            amount=received_amount,
            account=to_account,
            income_source=PersonalIncomeSource.TRANSFER,
            description=f"Transfer from {from_account.name}",
            reason=transfer_data['description'],
            date=transfer.date,
            reference_number=transfer.reference_number,
            affects_profit=False,
        )

        # Create fee transaction if there's a fee
        fee_transaction = None
        if transfer_fee > 0:
            fee_transaction = PersonalTransaction.objects.create(
                user=user,
                type=TransactionType.EXPENSE,
                amount=transfer_fee,
                account=from_account,
                expense_category=PersonalExpenseCategory.TRANSFER_FEE,
                description=f"Transfer fee for {to_account.name}",
                reason=f"Transfer fee: {transfer_data['description']}",
                date=transfer.date,
                reference_number=transfer.reference_number,
                affects_profit=True,
            )

        # Link transactions to transfer
        transfer.debit_transaction = debit_transaction
        transfer.credit_transaction = credit_transaction
        transfer.fee_transaction = fee_transaction
        transfer.save()

        return transfer

    @staticmethod
    def create_personal_debt(user, debt_data):
        """Create a personal debt record"""
        from finance.models import PersonalDebt
        from decimal import Decimal

        debt = PersonalDebt.objects.create(
            user=user,
            creditor_name=debt_data['creditor_name'],
            creditor_contact=debt_data.get('creditor_contact', ''),
            principal_amount=Decimal(str(debt_data['principal_amount'])),
            current_balance=Decimal(str(debt_data.get('current_balance', debt_data['principal_amount']))),
            interest_rate=Decimal(str(debt_data.get('interest_rate', 0))),
            has_interest=debt_data.get('has_interest', False),
            borrowed_date=debt_data['borrowed_date'],
            due_date=debt_data['due_date'],
            description=debt_data.get('description', ''),
            notes=debt_data.get('notes', '')
        )

        return debt

    @staticmethod
    def create_personal_loan(user, loan_data):
        """Create a personal loan record and debit transaction"""
        from finance.models import PersonalLoan, PersonalTransaction, Account
        from common.enums import FinanceScope, TransactionType, PersonalExpenseCategory
        from decimal import Decimal

        # Validate account
        account_value = loan_data.get('account')
        if isinstance(account_value, Account):
            account = account_value
        else:
            account = Account.objects.get(
                id=account_value,
                scope=FinanceScope.PERSONAL,
                owner=user
            )

        loan = PersonalLoan.objects.create(
            user=user,
            borrower_name=loan_data['borrower_name'],
            borrower_contact=loan_data.get('borrower_contact', ''),
            principal_amount=Decimal(str(loan_data['principal_amount'])),
            current_balance=Decimal(str(loan_data.get('current_balance', loan_data['principal_amount']))),
            interest_rate=Decimal(str(loan_data.get('interest_rate', 0))),
            has_interest=loan_data.get('has_interest', False),
            loan_date=loan_data['loan_date'],
            due_date=loan_data['due_date'],
            description=loan_data.get('description', ''),
            notes=loan_data.get('notes', '')
        )

        # Create expense transaction for the loan given
        PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.EXPENSE,
            amount=loan.principal_amount,
            account=account,
            expense_category=PersonalExpenseCategory.LOAN_GIVEN,
            description=f"Loan given to {loan.borrower_name}",
            reason=loan.description or f"Personal loan to {loan.borrower_name}",
            date=loan.loan_date,
            affects_profit=False,
        )

        return loan

    @staticmethod
    def make_debt_payment(user, debt_id, payment_data):
        """Make a payment towards a debt"""
        from finance.models import PersonalDebt, DebtPayment, Account
        from common.enums import FinanceScope
        from decimal import Decimal

        debt = PersonalDebt.objects.get(id=debt_id, user=user)
        account_obj = payment_data.get('account')
        if isinstance(account_obj, Account):
            account = account_obj
        else:
            account = Account.objects.get(
                id=account_obj,
                scope=FinanceScope.PERSONAL,
                owner=user
            )

        amount = Decimal(str(payment_data['amount'])).quantize(Decimal('0.01'))
        if amount <= 0:
            raise ValidationError({'amount': 'Payment amount must be greater than zero'})

        interest_amount = Decimal(str(payment_data.get('interest_amount', 0))).quantize(Decimal('0.01'))
        if interest_amount < 0:
            raise ValidationError({'interest_amount': 'Interest amount cannot be negative'})

        principal_amount = amount - interest_amount
        if principal_amount < 0:
            raise ValidationError({'interest_amount': 'Interest cannot exceed total payment'})

        if principal_amount > debt.remaining_balance:
            raise ValidationError({'amount': 'Principal component exceeds remaining debt balance'})

        if principal_amount == 0 and interest_amount == 0:
            raise ValidationError({'amount': 'Payment must include either principal or interest'})

        payment = DebtPayment.objects.create(
            debt=debt,
            amount=amount,
            account=account,
            payment_date=payment_data.get('payment_date', timezone.now().date()),
            notes=payment_data.get('notes', ''),
            principal_amount=principal_amount,
            interest_amount=interest_amount,
        )

        # Check if debt is fully paid and update status
        if debt.remaining_balance <= 0:
            debt.is_fully_paid = True
            debt.paid_date = payment.payment_date
            debt.is_active = False
            debt.save()

        return payment

    @staticmethod
    def receive_loan_repayment(user, loan_id, repayment_data):
        """Receive a repayment for a loan"""
        from finance.models import PersonalLoan, LoanRepayment, Account
        from common.enums import FinanceScope
        from decimal import Decimal

        loan = PersonalLoan.objects.get(id=loan_id, user=user)
        account_obj = repayment_data.get('account')
        if isinstance(account_obj, Account):
            account = account_obj
        else:
            account = Account.objects.get(
                id=account_obj,
                scope=FinanceScope.PERSONAL,
                owner=user
            )

        amount = Decimal(str(repayment_data['amount'])).quantize(Decimal('0.01'))
        if amount <= 0:
            raise ValidationError({'amount': 'Repayment amount must be greater than zero'})

        interest_amount = Decimal(str(repayment_data.get('interest_amount', 0))).quantize(Decimal('0.01'))
        if interest_amount < 0:
            raise ValidationError({'interest_amount': 'Interest amount cannot be negative'})

        principal_amount = amount - interest_amount
        if principal_amount < 0:
            raise ValidationError({'interest_amount': 'Interest cannot exceed total repayment'})

        if principal_amount > loan.remaining_balance:
            raise ValidationError({'amount': 'Principal component exceeds remaining loan balance'})

        if principal_amount == 0 and interest_amount == 0:
            raise ValidationError({'amount': 'Repayment must include either principal or interest'})

        repayment = LoanRepayment.objects.create(
            loan=loan,
            amount=amount,
            account=account,
            repayment_date=repayment_data.get('repayment_date', timezone.now().date()),
            notes=repayment_data.get('notes', ''),
            principal_amount=principal_amount,
            interest_amount=interest_amount,
        )

        # Check if loan is fully repaid and update status
        if loan.remaining_balance <= 0:
            loan.is_fully_repaid = True
            loan.repaid_date = repayment.repayment_date
            loan.is_active = False
            loan.save()

        return repayment

    @staticmethod
    def get_debt_summary(user):
        """Get summary of all debts and loans"""
        from finance.models import PersonalDebt, PersonalLoan
        from django.db.models import Sum
        from decimal import Decimal

        # Active debts (money owed)
        active_debts = PersonalDebt.objects.filter(user=user, is_active=True)
        total_debt_balance = sum(debt.remaining_balance for debt in active_debts)
        overdue_debts = [debt for debt in active_debts if debt.is_overdue]

        # Active loans (money lent out)
        active_loans = PersonalLoan.objects.filter(user=user, is_active=True)
        total_loan_balance = sum(loan.remaining_balance for loan in active_loans)
        overdue_loans = [loan for loan in active_loans if loan.is_overdue]

        return {
            'total_debt_owed': total_debt_balance,
            'total_loans_outstanding': total_loan_balance,
            'net_debt_position': total_debt_balance - total_loan_balance,
            'active_debts_count': active_debts.count(),
            'active_loans_count': active_loans.count(),
            'overdue_debts_count': len(overdue_debts),
            'overdue_loans_count': len(overdue_loans),
            'overdue_debts': overdue_debts,
            'overdue_loans': overdue_loans
        }

    @staticmethod
    def get_interest_summary(user, start_date=None, end_date=None):
        """Aggregate interest paid and received within an optional date range"""
        from finance.models import PersonalTransaction
        from django.db.models import Sum
        from decimal import Decimal
        from common.enums import PersonalExpenseCategory, PersonalIncomeSource, TransactionType

        transactions = PersonalTransaction.objects.filter(user=user, affects_profit=True)

        if start_date:
            transactions = transactions.filter(date__date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__date__lte=end_date)

        interest_paid_qs = transactions.filter(
            type=TransactionType.EXPENSE,
            expense_category=PersonalExpenseCategory.DEBT_INTEREST,
        )
        interest_received_qs = transactions.filter(
            type=TransactionType.INCOME,
            income_source=PersonalIncomeSource.LOAN_INTEREST,
        )

        total_interest_paid = interest_paid_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_interest_received = interest_received_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return {
            'total_interest_paid': total_interest_paid,
            'total_interest_received': total_interest_received,
            'net_interest': total_interest_received - total_interest_paid,
            'interest_paid_transactions': interest_paid_qs.count(),
            'interest_received_transactions': interest_received_qs.count(),
            'start_date': start_date,
            'end_date': end_date,
        }
