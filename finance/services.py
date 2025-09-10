from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone
from django.db import models

from finance.models import Payment, Transaction, Invoice
from common.enums import TransactionType, PaymentMethod, InvoiceDirection


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

        # Map invoice direction to transaction type
        # Paying INCOMING invoice => EXPENSE; Paying OUTGOING invoice => INCOME
        tx_type = TransactionType.EXPENSE if invoice.direction == InvoiceDirection.INCOMING else TransactionType.INCOME
        tx = Transaction.objects.create(
            type=tx_type,
            amount=amount,
            description=notes or f"Payment for invoice {invoice.number}",
            account=account,
            related_invoice=invoice,
            related_payment=payment,
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

        # Validate account ownership
        account = Account.objects.get(
            id=transaction_data['account'],
            scope=FinanceScope.PERSONAL,
            owner=user
        )

        # Create transaction
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
        )

        # Update account balance
        PersonalFinanceService.update_account_balance(account, transaction)

        # Update related budgets
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
            budget.save()  # This triggers recalculation of spent_amount

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
        income_transactions = transactions.filter(type=TransactionType.INCOME)
        expense_transactions = transactions.filter(type=TransactionType.EXPENSE)

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

        income_transactions = transactions.filter(type=TransactionType.INCOME)
        expense_transactions = transactions.filter(type=TransactionType.EXPENSE)

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

        # Validate accounts
        from_account = Account.objects.get(
            id=transfer_data['from_account'],
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        to_account = Account.objects.get(
            id=transfer_data['to_account'],
            scope=FinanceScope.PERSONAL,
            owner=user
        )

        if from_account == to_account:
            raise ValidationError("Cannot transfer to the same account")

        amount = Decimal(str(transfer_data['amount']))
        transfer_fee = Decimal(str(transfer_data.get('transfer_fee', 0)))

        # Create the transfer record
        transfer = PersonalAccountTransfer.objects.create(
            user=user,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            transfer_fee=transfer_fee,
            exchange_rate=Decimal(str(transfer_data.get('exchange_rate', 1))),
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
            reference_number=transfer.reference_number
        )

        # Create credit transaction (amount to destination account)
        credit_transaction = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.INCOME,
            amount=amount,
            account=to_account,
            income_source=PersonalIncomeSource.TRANSFER,
            description=f"Transfer from {from_account.name}",
            reason=transfer_data['description'],
            date=transfer.date,
            reference_number=transfer.reference_number
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
                reference_number=transfer.reference_number
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
        account = Account.objects.get(
            id=loan_data['account'],
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
            date=loan.loan_date
        )

        return loan

    @staticmethod
    def make_debt_payment(user, debt_id, payment_data):
        """Make a payment towards a debt"""
        from finance.models import PersonalDebt, DebtPayment, Account
        from common.enums import FinanceScope
        from decimal import Decimal

        debt = PersonalDebt.objects.get(id=debt_id, user=user)
        account = Account.objects.get(
            id=payment_data['account'],
            scope=FinanceScope.PERSONAL,
            owner=user
        )

        amount = Decimal(str(payment_data['amount']))

        if amount > debt.remaining_balance:
            raise ValidationError("Payment amount cannot exceed remaining debt balance")

        payment = DebtPayment.objects.create(
            debt=debt,
            amount=amount,
            account=account,
            payment_date=payment_data.get('payment_date', timezone.now().date()),
            notes=payment_data.get('notes', '')
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
        account = Account.objects.get(
            id=repayment_data['account'],
            scope=FinanceScope.PERSONAL,
            owner=user
        )

        amount = Decimal(str(repayment_data['amount']))

        if amount > loan.remaining_balance:
            raise ValidationError("Repayment amount cannot exceed remaining loan balance")

        repayment = LoanRepayment.objects.create(
            loan=loan,
            amount=amount,
            account=account,
            repayment_date=repayment_data.get('repayment_date', timezone.now().date()),
            notes=repayment_data.get('notes', '')
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
