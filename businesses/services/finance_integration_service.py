from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from businesses.models import Sale
from finance.models import Transaction, Account
from businesses.services.business_service import BusinessService


class BusinessFinanceService:
    """
    Integration between Business module and Finance module.
    Creates finance transactions for business activities.
    Phase 4: Finance Integration
    """
    
    @staticmethod
    @transaction.atomic
    def record_sale_transaction(sale):
        """
        Create finance transaction(s) for a completed sale.
        
        This creates journal entries following double-entry bookkeeping:
        - DR: Cash/Bank (Asset) - increases
        - CR: Sales Revenue (Revenue) - increases
        - DR: Cost of Goods Sold (Expense) - increases
        - CR: Inventory (Asset) - decreases
        
        Args:
            sale: Sale instance (must be completed)
        
        Returns:
            dict with created transactions
        
        Raises:
            ValueError: If sale is not completed or config disables finance entries
        """
        if sale.status != 'completed':
            raise ValueError("Can only create finance transactions for completed sales")
        
        config = sale.enterprise.configuration
        if not config.auto_create_finance_entries:
            raise ValueError("Auto-create finance entries is disabled for this enterprise")
        
        # Check if transaction already exists
        if sale.finance_transaction:
            raise ValueError(f"Finance transaction already exists for sale #{sale.sale_number}")
        
        # Get business accounts
        accounts = BusinessService.get_business_accounts(sale.enterprise)
        
        if not accounts:
            raise ValueError(f"No finance accounts found for enterprise {sale.enterprise.name}")
        
        # 1. Record cash received and revenue
        # DR: Cash Box (increases asset)
        cash_transaction = Transaction.objects.create(
            type='income',
            amount=sale.total_amount,
            description=f"Sale #{sale.sale_number} - {sale.customer_name or 'Walk-in customer'}",
            account=accounts.get('cash'),
            category='sales',
            date=sale.sale_date,
            is_automated=True
        )
        
        # Link to sale
        sale.finance_transaction = cash_transaction
        sale.save(update_fields=['finance_transaction'])
        
        # 2. Record cost of goods sold
        # DR: COGS (increases expense), CR: Inventory (decreases asset)
        total_cost = sale.total_cost
        
        if total_cost > 0:
            # COGS expense
            cogs_transaction = Transaction.objects.create(
                type='expense',
                amount=total_cost,
                description=f"Cost of goods for Sale #{sale.sale_number}",
                account=accounts.get('cogs'),
                category='cogs',
                date=sale.sale_date,
                is_automated=True
            )
        else:
            cogs_transaction = None
        
        return {
            'revenue_transaction': cash_transaction,
            'cogs_transaction': cogs_transaction,
            'total_revenue': sale.total_amount,
            'total_cost': total_cost,
            'profit': sale.profit
        }
    
    @staticmethod
    @transaction.atomic
    def record_stock_purchase(enterprise, amount, description, date=None):
        """
        Record a stock purchase as a finance transaction.
        DR: Inventory (Asset), CR: Cash/Bank
        
        Args:
            enterprise: SaccoEnterprise instance
            amount: Purchase amount
            description: Description of purchase
            date: Transaction date (defaults to today)
        
        Returns:
            Transaction instance
        """
        accounts = BusinessService.get_business_accounts(enterprise)
        
        if not accounts:
            raise ValueError(f"No finance accounts found for enterprise {enterprise.name}")
        
        # Record as expense (cash outflow for inventory purchase)
        purchase_transaction = Transaction.objects.create(
            type='expense',
            amount=amount,
            description=f"Stock purchase: {description}",
            account=accounts.get('cash'),
            category='inventory',
            date=date or timezone.now().date(),
            is_automated=True
        )
        
        return purchase_transaction
    
    @staticmethod
    @transaction.atomic
    def record_business_expense(enterprise, amount, description, category='operations', date=None):
        """
        Record a general business expense.
        DR: Operating Expenses (Expense), CR: Cash
        
        Args:
            enterprise: SaccoEnterprise instance
            amount: Expense amount
            description: Description of expense
            category: Expense category
            date: Transaction date (defaults to today)
        
        Returns:
            Transaction instance
        """
        accounts = BusinessService.get_business_accounts(enterprise)
        
        if not accounts:
            raise ValueError(f"No finance accounts found for enterprise {enterprise.name}")
        
        expense_transaction = Transaction.objects.create(
            type='expense',
            amount=amount,
            description=description,
            account=accounts.get('expenses'),
            category=category,
            date=date or timezone.now().date(),
            is_automated=True
        )
        
        return expense_transaction
    
    @staticmethod
    def get_profit_and_loss(enterprise, start_date, end_date):
        """
        Calculate profit and loss for an enterprise within a date range.
        
        Args:
            enterprise: SaccoEnterprise instance
            start_date: Start date
            end_date: End date
        
        Returns:
            dict with P&L data
        """
        from django.db.models import Sum, Q
        
        accounts = BusinessService.get_business_accounts(enterprise)
        
        if not accounts:
            return {
                'revenue': Decimal('0'),
                'cogs': Decimal('0'),
                'expenses': Decimal('0'),
                'gross_profit': Decimal('0'),
                'net_profit': Decimal('0'),
                'profit_margin': Decimal('0')
            }
        
        # Get all revenue
        revenue = Transaction.objects.filter(
            account=accounts.get('revenue'),
            type='income',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Get COGS
        cogs = Transaction.objects.filter(
            account=accounts.get('cogs'),
            type='expense',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Get operating expenses
        expenses = Transaction.objects.filter(
            account=accounts.get('expenses'),
            type='expense',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Calculate profits
        gross_profit = revenue - cogs
        net_profit = gross_profit - expenses
        profit_margin = (net_profit / revenue * 100) if revenue > 0 else Decimal('0')
        
        return {
            'revenue': revenue,
            'cogs': cogs,
            'expenses': expenses,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'start_date': start_date,
            'end_date': end_date
        }
    
    @staticmethod
    def get_cash_flow(enterprise, start_date, end_date):
        """
        Calculate cash flow for an enterprise within a date range.
        
        Args:
            enterprise: SaccoEnterprise instance
            start_date: Start date
            end_date: End date
        
        Returns:
            dict with cash flow data
        """
        from django.db.models import Sum
        
        accounts = BusinessService.get_business_accounts(enterprise)
        
        if not accounts or not accounts.get('cash'):
            return {
                'opening_balance': Decimal('0'),
                'cash_in': Decimal('0'),
                'cash_out': Decimal('0'),
                'net_cash_flow': Decimal('0'),
                'closing_balance': Decimal('0')
            }
        
        cash_account = accounts.get('cash')
        
        # Opening balance (balance before start_date)
        opening_transactions_in = Transaction.objects.filter(
            account=cash_account,
            type='income',
            date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        opening_transactions_out = Transaction.objects.filter(
            account=cash_account,
            type='expense',
            date__lt=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        opening_balance = opening_transactions_in - opening_transactions_out
        
        # Cash inflows in period
        cash_in = Transaction.objects.filter(
            account=cash_account,
            type='income',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Cash outflows in period
        cash_out = Transaction.objects.filter(
            account=cash_account,
            type='expense',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Net cash flow
        net_cash_flow = cash_in - cash_out
        closing_balance = opening_balance + net_cash_flow
        
        return {
            'opening_balance': opening_balance,
            'cash_in': cash_in,
            'cash_out': cash_out,
            'net_cash_flow': net_cash_flow,
            'closing_balance': closing_balance,
            'start_date': start_date,
            'end_date': end_date
        }
