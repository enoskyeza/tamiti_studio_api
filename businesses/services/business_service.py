from django.db import transaction
from decimal import Decimal

from businesses.models import SaccoEnterprise, EnterpriseConfiguration
from finance.models import Account


class BusinessService:
    """
    Core business operations and setup.
    Phase 1: Business Module
    """
    
    @staticmethod
    @transaction.atomic
    def create_business(sacco, name, business_type, **kwargs):
        """
        Create a new business with proper setup.
        Automatically creates:
        - Enterprise record
        - Configuration record
        - Finance accounts (chart of accounts)
        
        Args:
            sacco: SaccoOrganization instance
            name: Business name
            business_type: Type of business
            **kwargs: Additional fields (description, phone, email, location)
        
        Returns:
            SaccoEnterprise instance with configuration and accounts set up
        """
        # Create enterprise
        enterprise = SaccoEnterprise.objects.create(
            sacco=sacco,
            name=name,
            business_type=business_type,
            description=kwargs.get('description', ''),
            phone=kwargs.get('phone', ''),
            email=kwargs.get('email', ''),
            location=kwargs.get('location', ''),
        )
        
        # Create configuration with defaults
        EnterpriseConfiguration.objects.create(
            enterprise=enterprise
        )
        
        # Setup finance accounts
        BusinessService.setup_finance_accounts(enterprise)
        
        return enterprise
    
    @staticmethod
    @transaction.atomic
    def setup_finance_accounts(enterprise):
        """
        Create standard chart of accounts for this business.
        Reuses existing Finance app structure.
        
        Creates:
        - Cash Box (Asset)
        - Inventory (Asset)
        - Sales Revenue (Revenue)
        - Cost of Goods Sold (Expense)
        - Operating Expenses (Expense)
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            dict of created accounts
        """
        # Create business-specific accounts using company scope
        business_accounts = {}
        
        # 1. Cash Box (main operating account)
        business_accounts['cash'] = Account.objects.create(
            name=f"{enterprise.name} - Cash Box",
            type='asset',
            scope='company',
            domain='sacco',
            description=f"Daily cash operations for {enterprise.name} business",
        )
        
        # 2. Inventory Asset
        business_accounts['inventory'] = Account.objects.create(
            name=f"{enterprise.name} - Inventory",
            type='asset',
            scope='company',
            domain='sacco',
            description=f"Stock on hand for {enterprise.name}",
        )
        
        # 3. Sales Revenue
        business_accounts['revenue'] = Account.objects.create(
            name=f"{enterprise.name} - Sales Revenue",
            type='revenue',
            scope='company',
            domain='sacco',
            description=f"Income from sales for {enterprise.name}",
        )
        
        # 4. Cost of Goods Sold
        business_accounts['cogs'] = Account.objects.create(
            name=f"{enterprise.name} - Cost of Goods Sold",
            type='expense',
            scope='company',
            domain='sacco',
            description=f"Cost of items sold for {enterprise.name}",
        )
        
        # 5. Operating Expenses
        business_accounts['expenses'] = Account.objects.create(
            name=f"{enterprise.name} - Operating Expenses",
            type='expense',
            scope='company',
            domain='sacco',
            description=f"General business expenses for {enterprise.name}",
        )
        
        # Set main account (Cash Box) on enterprise
        enterprise.finance_account = business_accounts['cash']
        enterprise.save(update_fields=['finance_account'])
        
        return business_accounts
    
    @staticmethod
    def get_business_accounts(enterprise):
        """
        Get all finance accounts for a business.
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            dict with keys: cash, inventory, revenue, cogs, expenses
        """
        accounts = Account.objects.filter(
            scope='company',
            name__startswith=enterprise.name
        )
        
        account_map = {}
        for account in accounts:
            if 'Cash Box' in account.name:
                account_map['cash'] = account
            elif 'Inventory' in account.name:
                account_map['inventory'] = account
            elif 'Revenue' in account.name:
                account_map['revenue'] = account
            elif 'Cost of Goods' in account.name:
                account_map['cogs'] = account
            elif 'Operating Expenses' in account.name:
                account_map['expenses'] = account
        
        return account_map
    
    @staticmethod
    @transaction.atomic
    def update_configuration(enterprise, **config_updates):
        """
        Update enterprise configuration.
        
        Args:
            enterprise: SaccoEnterprise instance
            **config_updates: Fields to update on configuration
        
        Returns:
            Updated EnterpriseConfiguration instance
        """
        config = enterprise.configuration
        
        for key, value in config_updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.save()
        return config
    
    @staticmethod
    def archive_business(enterprise):
        """
        Soft delete a business (set is_active=False).
        Does NOT delete financial records.
        
        Args:
            enterprise: SaccoEnterprise instance
        """
        enterprise.is_active = False
        enterprise.save(update_fields=['is_active'])
