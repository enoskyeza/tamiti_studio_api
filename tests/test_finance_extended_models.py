# tests/test_finance_extended_models.py
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import IntegrityError

from finance.models import (
    PersonalTransaction, PersonalBudget, PersonalSavingsGoal,
    PersonalTransactionRecurring, PersonalAccountTransfer,
    PersonalDebt, PersonalLoan, InvoiceItem, QuotationItem,
    ReceiptItem, Quotation, Receipt, Account, Party
)
from common.enums import (
    TransactionType, PersonalExpenseCategory, PersonalIncomeSource,
    BudgetPeriod, FinanceScope, Currency, PaymentMethod, QuotationStatus
)
from tests.factories import UserFactory, AccountFactory, PartyFactory


@pytest.mark.django_db
class TestFinanceExtendedModels:

    def test_personal_transaction_creation_income(self):
        """Test PersonalTransaction creation for income"""
        user = UserFactory()
        account = Account.objects.create(
            name="Personal Checking",
            type="bank",
            scope=FinanceScope.PERSONAL,
            owner=user,
            balance=Decimal('1000.00')
        )
        
        transaction = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.INCOME,
            amount=Decimal('500.00'),
            account=account,
            description="Freelance payment",
            transaction_charge=Decimal('5.00'),
            income_source=PersonalIncomeSource.FREELANCE,
            reason="Web development project",
            reference_number="REF123",
            tags=["freelance", "web-dev"],
            location="Home office"
        )
        
        assert transaction.user == user
        assert transaction.type == TransactionType.INCOME
        assert transaction.amount == Decimal('500.00')
        assert transaction.account == account
        assert transaction.description == "Freelance payment"
        assert transaction.transaction_charge == Decimal('5.00')
        assert transaction.income_source == PersonalIncomeSource.FREELANCE
        assert transaction.reason == "Web development project"
        assert transaction.reference_number == "REF123"
        assert transaction.tags == ["freelance", "web-dev"]
        assert transaction.location == "Home office"
        assert transaction.total_cost == Decimal('505.00')

    def test_personal_transaction_creation_expense(self):
        """Test PersonalTransaction creation for expense"""
        user = UserFactory()
        account = Account.objects.create(
            name="Personal Savings",
            type="savings",
            scope=FinanceScope.PERSONAL,
            owner=user,
            balance=Decimal('2000.00')
        )
        
        transaction = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.EXPENSE,
            amount=Decimal('150.00'),
            account=account,
            description="Grocery shopping",
            expense_category=PersonalExpenseCategory.FOOD,
            reason="Weekly groceries",
            notes="Bought organic vegetables"
        )
        
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.expense_category == PersonalExpenseCategory.FOOD
        assert transaction.income_source == ""
        assert transaction.notes == "Bought organic vegetables"

    def test_personal_transaction_validation_income_requires_source(self):
        """Test PersonalTransaction validation for income source"""
        user = UserFactory()
        account = Account.objects.create(
            name="Test Account",
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        
        transaction = PersonalTransaction(
            user=user,
            type=TransactionType.INCOME,
            amount=Decimal('100.00'),
            account=account,
            description="Test income",
            reason="Test"
            # Missing income_source
        )
        
        with pytest.raises(ValidationError) as exc_info:
            transaction.clean()
        
        assert "Income source is required for income transactions" in str(exc_info.value)

    def test_personal_transaction_validation_expense_requires_category(self):
        """Test PersonalTransaction validation for expense category"""
        user = UserFactory()
        account = Account.objects.create(
            name="Test Account",
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        
        transaction = PersonalTransaction(
            user=user,
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            account=account,
            description="Test expense",
            reason="Test"
            # Missing expense_category
        )
        
        with pytest.raises(ValidationError) as exc_info:
            transaction.clean()
        
        assert "Expense category is required for expense transactions" in str(exc_info.value)

    def test_personal_transaction_validation_account_owner(self):
        """Test PersonalTransaction validation for account ownership"""
        user1 = UserFactory()
        user2 = UserFactory()
        account = Account.objects.create(
            name="User2 Account",
            scope=FinanceScope.PERSONAL,
            owner=user2
        )
        
        transaction = PersonalTransaction(
            user=user1,  # Different user than account owner
            type=TransactionType.EXPENSE,
            amount=Decimal('100.00'),
            account=account,
            description="Test",
            expense_category=PersonalExpenseCategory.FOOD,
            reason="Test"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            transaction.clean()
        
        assert "Account must belong to the transaction user" in str(exc_info.value)

    def test_personal_budget_creation_and_properties(self):
        """Test PersonalBudget model creation and properties"""
        user = UserFactory()
        start_date = timezone.now().date()
        end_date = start_date + timezone.timedelta(days=30)
        
        budget = PersonalBudget.objects.create(
            user=user,
            name="Monthly Food Budget",
            category=PersonalExpenseCategory.FOOD,
            period=BudgetPeriod.MONTHLY,
            allocated_amount=Decimal('500.00'),
            spent_amount=Decimal('200.00'),
            start_date=start_date,
            end_date=end_date,
            alert_threshold=Decimal('80.00')
        )
        
        assert str(budget) == "Monthly Food Budget - Food & Dining (Monthly)"
        assert budget.user == user
        assert budget.name == "Monthly Food Budget"
        assert budget.category == PersonalExpenseCategory.FOOD
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.allocated_amount == Decimal('500.00')
        assert budget.spent_amount == Decimal('200.00')
        assert budget.remaining_amount == Decimal('300.00')
        assert budget.progress_percentage == Decimal('40.00')
        assert not budget.is_exceeded
        assert not budget.should_alert

    def test_personal_budget_exceeded_and_alert(self):
        """Test PersonalBudget exceeded and alert conditions"""
        user = UserFactory()
        
        budget = PersonalBudget.objects.create(
            user=user,
            name="Overspent Budget",
            category=PersonalExpenseCategory.ENTERTAINMENT,
            allocated_amount=Decimal('100.00'),
            spent_amount=Decimal('120.00'),  # Exceeded
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=30),
            alert_threshold=Decimal('70.00')
        )
        
        assert budget.is_exceeded
        assert budget.should_alert
        assert budget.remaining_amount == Decimal('0.00')
        assert budget.progress_percentage == Decimal('120.00')

    def test_personal_savings_goal_creation_and_properties(self):
        """Test PersonalSavingsGoal model creation and properties"""
        user = UserFactory()
        target_date = timezone.now().date() + timezone.timedelta(days=365)
        
        goal = PersonalSavingsGoal.objects.create(
            user=user,
            name="Emergency Fund",
            description="Build 6-month emergency fund",
            target_amount=Decimal('10000.00'),
            current_amount=Decimal('2500.00'),
            target_date=target_date,
            auto_save_amount=Decimal('500.00'),
            auto_save_frequency=BudgetPeriod.MONTHLY
        )
        
        assert str(goal) == "Emergency Fund - 25.0% complete"
        assert goal.user == user
        assert goal.name == "Emergency Fund"
        assert goal.description == "Build 6-month emergency fund"
        assert goal.target_amount == Decimal('10000.00')
        assert goal.current_amount == Decimal('2500.00')
        assert goal.remaining_amount == Decimal('7500.00')
        assert goal.progress_percentage == Decimal('25.00')
        assert not goal.is_achieved
        assert goal.auto_save_amount == Decimal('500.00')
        assert goal.auto_save_frequency == BudgetPeriod.MONTHLY

    def test_personal_savings_goal_add_contribution(self):
        """Test PersonalSavingsGoal add_contribution method"""
        user = UserFactory()
        account = Account.objects.create(
            name="Savings Account",
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        
        goal = PersonalSavingsGoal.objects.create(
            user=user,
            name="Vacation Fund",
            target_amount=Decimal('1000.00'),
            current_amount=Decimal('800.00'),
            target_date=timezone.now().date() + timezone.timedelta(days=90)
        )
        
        # Add contribution that completes the goal
        goal.add_contribution(Decimal('200.00'), "Final contribution")
        
        assert goal.current_amount == Decimal('1000.00')
        assert goal.is_achieved
        assert goal.achieved_date is not None

    def test_personal_debt_creation_and_properties(self):
        """Test PersonalDebt model creation and properties"""
        user = UserFactory()
        borrowed_date = timezone.now().date() - timezone.timedelta(days=30)
        due_date = timezone.now().date() + timezone.timedelta(days=60)
        
        debt = PersonalDebt.objects.create(
            user=user,
            creditor_name="John Doe",
            creditor_contact="john@example.com",
            principal_amount=Decimal('5000.00'),
            current_balance=Decimal('5000.00'),
            interest_rate=Decimal('5.00'),
            has_interest=True,
            borrowed_date=borrowed_date,
            due_date=due_date,
            description="Personal loan for car repair"
        )
        
        assert str(debt) == "Debt to John Doe: 5000.00/5000.00"
        assert debt.user == user
        assert debt.creditor_name == "John Doe"
        assert debt.creditor_contact == "john@example.com"
        assert debt.principal_amount == Decimal('5000.00')
        assert debt.current_balance == Decimal('5000.00')
        assert debt.interest_rate == Decimal('5.00')
        assert debt.has_interest
        assert debt.borrowed_date == borrowed_date
        assert debt.due_date == due_date
        assert debt.is_active
        assert not debt.is_fully_paid
        assert debt.total_paid == Decimal('0.00')
        assert debt.remaining_balance == Decimal('5000.00')

    def test_quotation_creation_and_methods(self):
        """Test Quotation model creation and methods"""
        party = PartyFactory()
        
        quotation = Quotation.objects.create(
            party=party,
            quote_number="Q2024-001",
            total_amount=Decimal('1500.00'),
            description="Website development quotation",
            valid_until=timezone.now().date() + timezone.timedelta(days=30),
            status=QuotationStatus.DRAFT
        )
        
        assert str(quotation) == f"Quotation #Q2024-001 - {party.name}"
        assert quotation.party == party
        assert quotation.quote_number == "Q2024-001"
        assert quotation.total_amount == Decimal('1500.00')
        assert quotation.description == "Website development quotation"
        assert quotation.status == QuotationStatus.DRAFT

    def test_quotation_item_creation_and_calculation(self):
        """Test QuotationItem model and amount calculation"""
        party = PartyFactory()
        quotation = Quotation.objects.create(
            party=party,
            total_amount=Decimal('0.00')
        )
        
        item = QuotationItem.objects.create(
            quotation=quotation,
            name="Web Development",
            description="Custom website development",
            quantity=Decimal('40.00'),  # 40 hours
            unit_cost=Decimal('50.00')  # $50 per hour
        )
        
        assert item.name == "Web Development"
        assert item.description == "Custom website development"
        assert item.quantity == Decimal('40.00')
        assert item.unit_cost == Decimal('50.00')
        assert item.amount == Decimal('2000.00')  # 40 * 50
        
        # Check that quotation total was updated
        quotation.refresh_from_db()
        assert quotation.total_amount == Decimal('2000.00')

    def test_receipt_creation_and_methods(self):
        """Test Receipt model creation and methods"""
        party = PartyFactory()
        account = AccountFactory()
        
        receipt = Receipt.objects.create(
            number="RCP-001",
            party=party,
            amount=Decimal('750.00'),
            account=account,
            method=PaymentMethod.BANK_TRANSFER,
            reference="TXN123456",
            notes="Payment for services rendered"
        )
        
        assert str(receipt) == f"Receipt RCP-001 - {party.name}"
        assert receipt.number == "RCP-001"
        assert receipt.party == party
        assert receipt.amount == Decimal('750.00')
        assert receipt.account == account
        assert receipt.method == PaymentMethod.BANK_TRANSFER
        assert receipt.reference == "TXN123456"
        assert receipt.notes == "Payment for services rendered"

    def test_invoice_item_creation_and_calculation(self):
        """Test InvoiceItem model and amount calculation"""
        from finance.models import Invoice
        party = PartyFactory()
        
        invoice = Invoice.objects.create(
            party=party,
            direction="outgoing",
            subtotal=Decimal('0.00'),
            total=Decimal('0.00')
        )
        
        item = InvoiceItem.objects.create(
            invoice=invoice,
            name="Consulting Services",
            description="Business consulting",
            quantity=Decimal('10.00'),
            unit_cost=Decimal('100.00')
        )
        
        assert item.amount == Decimal('1000.00')  # 10 * 100
        
        # Check that invoice totals were updated
        invoice.refresh_from_db()
        assert invoice.subtotal == Decimal('1000.00')
        assert invoice.total == Decimal('1000.00')

    def test_personal_account_transfer_creation_and_validation(self):
        """Test PersonalAccountTransfer model"""
        user = UserFactory()
        from_account = Account.objects.create(
            name="Checking",
            scope=FinanceScope.PERSONAL,
            owner=user,
            balance=Decimal('1000.00')
        )
        to_account = Account.objects.create(
            name="Savings",
            scope=FinanceScope.PERSONAL,
            owner=user,
            balance=Decimal('500.00')
        )
        
        transfer = PersonalAccountTransfer.objects.create(
            user=user,
            from_account=from_account,
            to_account=to_account,
            amount=Decimal('200.00'),
            transfer_fee=Decimal('2.00'),
            description="Monthly savings transfer",
            reference_number="TRF123"
        )
        
        assert str(transfer) == "Transfer: 200.00 from Checking to Savings"
        assert transfer.user == user
        assert transfer.from_account == from_account
        assert transfer.to_account == to_account
        assert transfer.amount == Decimal('200.00')
        assert transfer.transfer_fee == Decimal('2.00')
        assert transfer.total_debit_amount == Decimal('202.00')
        assert transfer.description == "Monthly savings transfer"
        assert transfer.reference_number == "TRF123"

    def test_personal_account_transfer_validation_same_account(self):
        """Test PersonalAccountTransfer validation for same account"""
        user = UserFactory()
        account = Account.objects.create(
            name="Test Account",
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        
        transfer = PersonalAccountTransfer(
            user=user,
            from_account=account,
            to_account=account,  # Same account
            amount=Decimal('100.00'),
            description="Invalid transfer"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            transfer.clean()
        
        assert "Cannot transfer to the same account" in str(exc_info.value)

    def test_base_model_inheritance_all_models(self):
        """Test all extended finance models inherit BaseModel"""
        user = UserFactory()
        party = PartyFactory()
        account = Account.objects.create(
            name="Test Account",
            scope=FinanceScope.PERSONAL,
            owner=user
        )
        
        # Create instances of all models
        personal_tx = PersonalTransaction.objects.create(
            user=user,
            type=TransactionType.EXPENSE,
            amount=Decimal('50.00'),
            account=account,
            expense_category=PersonalExpenseCategory.FOOD,
            description="Test",
            reason="Test"
        )
        
        budget = PersonalBudget.objects.create(
            user=user,
            name="Test Budget",
            category=PersonalExpenseCategory.FOOD,
            allocated_amount=Decimal('100.00'),
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=30)
        )
        
        goal = PersonalSavingsGoal.objects.create(
            user=user,
            name="Test Goal",
            target_amount=Decimal('1000.00'),
            target_date=timezone.now().date() + timezone.timedelta(days=365)
        )
        
        quotation = Quotation.objects.create(
            party=party,
            total_amount=Decimal('500.00')
        )
        
        receipt = Receipt.objects.create(
            party=party,
            amount=Decimal('250.00')
        )
        
        models_to_test = [personal_tx, budget, goal, quotation, receipt]
        
        for obj in models_to_test:
            # Check BaseModel fields
            assert hasattr(obj, 'created_at')
            assert hasattr(obj, 'updated_at')
            assert hasattr(obj, 'deleted_at')
            assert hasattr(obj, 'is_deleted')
            assert hasattr(obj, 'uuid')
            
            # Check soft delete method
            assert hasattr(obj, 'soft_delete')
            
            # Test soft delete functionality
            obj.soft_delete()
            assert obj.is_deleted is True
            assert obj.deleted_at is not None
