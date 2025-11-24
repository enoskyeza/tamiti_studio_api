"""
SACCO Account Service
Handles creation and management of SACCO financial accounts
Integrates with the finance app's Account and Transaction models
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from finance.models import Account, Transaction
from common.enums import FinanceScope, AccountType, TransactionType, PaymentCategory
from saccos.models import SaccoAccount


class SaccoAccountService:
    """Service for managing SACCO financial accounts"""
    
    @staticmethod
    @transaction.atomic
    def get_or_create_sacco_account(sacco, account_details=None):
        """
        Get or create a SACCO's financial account
        
        Args:
            sacco: SaccoOrganization instance
            account_details: dict with optional fields (bank_name, bank_branch, account_number, account_type)
        
        Returns:
            SaccoAccount instance
        """
        # Try to get existing account
        try:
            return SaccoAccount.objects.get(sacco=sacco)
        except SaccoAccount.DoesNotExist:
            pass
        
        # Create new account
        account_details = account_details or {}
        
        # Create finance Account
        # Use COMPANY scope since SACCO accounts are organizational (not personal)
        finance_account = Account.objects.create(
            name=account_details.get('account_name') or f"{sacco.name} - Main Account",
            number=account_details.get('account_number', ''),
            type=account_details.get('account_type', AccountType.BANK),
            scope=FinanceScope.COMPANY,
            domain="sacco",
            balance=Decimal('0'),
            is_active=True,
            description=f"Main financial account for {sacco.name}"
        )
        
        # Create SaccoAccount link
        sacco_account = SaccoAccount.objects.create(
            sacco=sacco,
            account=finance_account,
            bank_name=account_details.get('bank_name', ''),
            bank_branch=account_details.get('bank_branch', ''),
            account_number=account_details.get('account_number', '')
        )
        
        return sacco_account
    
    @staticmethod
    @transaction.atomic
    def update_account_details(sacco_account, **kwargs):
        """
        Update SACCO account details
        
        Args:
            sacco_account: SaccoAccount instance
            **kwargs: Fields to update (bank_name, bank_branch, account_number, account_type, name)
        """
        # Update SaccoAccount fields
        if 'bank_name' in kwargs:
            sacco_account.bank_name = kwargs['bank_name']
        if 'bank_branch' in kwargs:
            sacco_account.bank_branch = kwargs['bank_branch']
        if 'account_number' in kwargs:
            sacco_account.account_number = kwargs['account_number']
            # Also update the finance account number
            sacco_account.account.number = kwargs['account_number']
        
        # Update finance Account fields
        if 'account_type' in kwargs:
            sacco_account.account.type = kwargs['account_type']
        if 'name' in kwargs:
            sacco_account.account.name = kwargs['name']
        # Also handle account_name for frontend compatibility
        if 'account_name' in kwargs:
            sacco_account.account.name = kwargs['account_name']
        
        sacco_account.account.save()
        sacco_account.save()
        
        return sacco_account
    
    @staticmethod
    @transaction.atomic
    def record_transaction(
        sacco_account,
        transaction_type,
        amount,
        category,
        description,
        date=None,
        related_meeting=None,
        related_loan=None,
        recorded_by=None
    ):
        """
        Record a transaction in the SACCO account
        
        Args:
            sacco_account: SaccoAccount instance
            transaction_type: 'income' or 'expense' (from TransactionType enum)
            amount: Decimal amount
            category: Transaction category (from PaymentCategory enum)
            description: Transaction description
            date: Transaction date (defaults to today)
            related_meeting: Optional WeeklyMeeting instance
            related_loan: Optional Loan instance
            recorded_by: Optional User who recorded this
        
        Returns:
            Transaction instance
        """
        if not date:
            date = timezone.now().date()
        
        # Create the transaction (will automatically update account balance)
        txn = Transaction.objects.create(
            type=transaction_type,
            amount=amount,
            description=description,
            account=sacco_account.account,
            category=category,
            date=date,
            is_automated=True
        )
        
        # Store related objects in description if needed
        # (Transaction model doesn't have meeting/loan fields, so we track in description)
        if related_meeting:
            txn.description += f" [Meeting #{related_meeting.week_number}, {related_meeting.year}]"
            txn.save()
        
        if related_loan:
            txn.description += f" [Loan #{related_loan.id}]"
            txn.save()
        
        return txn
    
    @staticmethod
    def get_balance(sacco_account):
        """Get current balance of SACCO account"""
        return sacco_account.current_balance
    
    @staticmethod
    def get_transactions(sacco_account, start_date=None, end_date=None, category=None):
        """
        Get transactions for a SACCO account
        
        Args:
            sacco_account: SaccoAccount instance
            start_date: Optional start date filter
            end_date: Optional end date filter
            category: Optional category filter
        
        Returns:
            QuerySet of Transaction objects
        """
        transactions = Transaction.objects.filter(account=sacco_account.account)
        
        if start_date:
            transactions = transactions.filter(date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date__lte=end_date)
        if category:
            transactions = transactions.filter(category=category)
        
        return transactions.order_by('-date', '-created_at')
    
    @staticmethod
    def get_account_summary(sacco_account, start_date=None, end_date=None):
        """
        Get summary of account activity
        
        Returns:
            dict with total_income, total_expense, net_change, current_balance
        """
        from django.db.models import Sum, Q
        
        transactions = SaccoAccountService.get_transactions(
            sacco_account, start_date, end_date
        )
        
        total_income = transactions.filter(
            type=TransactionType.INCOME
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_expense = transactions.filter(
            type=TransactionType.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'net_change': total_income - total_expense,
            'current_balance': sacco_account.current_balance,
            'transaction_count': transactions.count()
        }
