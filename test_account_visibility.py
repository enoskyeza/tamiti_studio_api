#!/usr/bin/env python
"""
Test script to verify account visibility and permission fixes
"""

import os
import sys
import django
from datetime import date, timedelta
from decimal import Decimal

# Setup Django
sys.path.append('/Users/enoskyeza/Desktop/Tamiti Digital Office/tamiti_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from finance.models import Account, PersonalDebt, Transaction
from common.enums import FinanceScope
from finance.models import AccountType
from permissions.models import Permission, PermissionType, PermissionScope
from permissions.services import PermissionService

User = get_user_model()

def test_account_visibility():
    """Test account visibility and permission controls"""
    
    print("🔍 Testing Account Visibility and Permissions...")
    
    # Get or create test users
    try:
        user1 = User.objects.filter(username__icontains='test').first()
        if not user1:
            user1 = User.objects.first()
        
        user2 = User.objects.exclude(id=user1.id).first() if User.objects.count() > 1 else None
        
        if not user1:
            print("❌ No users found. Create users first.")
            return
            
        print(f"✅ Using user1: {user1.username}")
        if user2:
            print(f"✅ Using user2: {user2.username}")
        else:
            print("⚠️  Only one user available - creating second user")
            user2 = User.objects.create_user(
                username='testuser2',
                email='test2@example.com',
                password='testpass123'
            )
            print(f"✅ Created user2: {user2.username}")
            
    except Exception as e:
        print(f"❌ Error setting up users: {e}")
        return
    
    # Clean up any existing test data
    Account.objects.filter(name__startswith='Test').delete()
    PersonalDebt.objects.filter(creditor_name__startswith='Test').delete()
    
    # Initialize variables to avoid scope issues
    personal_account1 = None
    personal_account2 = None
    company_account = None
    
    # Test Case 1: Personal Account Visibility
    print("\n📝 Test 1: Personal Account Visibility")
    try:
        # Create personal accounts for both users
        personal_account1 = Account.objects.create(
            name='Test Personal Account 1',
            type='savings',
            scope=FinanceScope.PERSONAL,
            owner=user1,
            balance=Decimal('1000.00')
        )
        
        personal_account2 = Account.objects.create(
            name='Test Personal Account 2', 
            type='checking',
            scope=FinanceScope.PERSONAL,
            owner=user2,
            balance=Decimal('2000.00')
        )
        
        # Test visibility from AccountViewSet perspective
        from finance.views import AccountViewSet
        from django.test import RequestFactory
        
        factory = RequestFactory()
        
        # User1 should only see their own personal account
        request1 = factory.get('/api/finance/accounts/')
        request1.user = user1
        viewset1 = AccountViewSet()
        viewset1.request = request1
        user1_accounts = viewset1.get_queryset()
        
        user1_personal_count = user1_accounts.filter(scope=FinanceScope.PERSONAL).count()
        print(f"✅ User1 sees {user1_personal_count} personal account(s)")
        
        # User2 should only see their own personal account
        request2 = factory.get('/api/finance/accounts/')
        request2.user = user2
        viewset2 = AccountViewSet()
        viewset2.request = request2
        user2_accounts = viewset2.get_queryset()
        
        user2_personal_count = user2_accounts.filter(scope=FinanceScope.PERSONAL).count()
        print(f"✅ User2 sees {user2_personal_count} personal account(s)")
        
        # Verify isolation
        user1_can_see_user2_account = user1_accounts.filter(id=personal_account2.id).exists()
        user2_can_see_user1_account = user2_accounts.filter(id=personal_account1.id).exists()
        
        if not user1_can_see_user2_account and not user2_can_see_user1_account:
            print("✅ Personal account isolation working correctly")
        else:
            print("❌ Personal account isolation failed")
            
    except Exception as e:
        print(f"❌ Personal account visibility test failed: {e}")
    
    # Test Case 2: Company Account Permissions
    print("\n📝 Test 2: Company Account Permissions")
    try:
        # Create a company account
        company_account = Account.objects.create(
            name='Test Company Account',
            type='checking',
            scope=FinanceScope.COMPANY,
            balance=Decimal('10000.00')
        )
        
        # Initially, both users should see company account (no permissions defined)
        user1_company_count = user1_accounts.filter(scope=FinanceScope.COMPANY).count()
        user2_company_count = user2_accounts.filter(scope=FinanceScope.COMPANY).count()
        
        print(f"✅ Before permissions: User1 sees {user1_company_count} company account(s)")
        print(f"✅ Before permissions: User2 sees {user2_company_count} company account(s)")
        
        # Create a permission that only allows user1 to read company accounts
        account_content_type = ContentType.objects.get_for_model(Account)
        permission = Permission.objects.create(
            name='Read Company Accounts',
            action='read',
            permission_type=PermissionType.ALLOW,
            scope=PermissionScope.GLOBAL,
            content_type=account_content_type,
            is_active=True
        )
        permission.users.add(user1)
        
        print("✅ Created permission allowing only user1 to read company accounts")
        
        # Test visibility after permission
        user1_accounts_after = viewset1.get_queryset()
        user2_accounts_after = viewset2.get_queryset()
        
        user1_company_after = user1_accounts_after.filter(scope=FinanceScope.COMPANY).count()
        user2_company_after = user2_accounts_after.filter(scope=FinanceScope.COMPANY).count()
        
        print(f"✅ After permissions: User1 sees {user1_company_after} company account(s)")
        print(f"✅ After permissions: User2 sees {user2_company_after} company account(s)")
        
        if user1_company_after > 0 and user2_company_after == 0:
            print("✅ Company account permissions working correctly")
        else:
            print("⚠️  Company account permissions may need adjustment")
            
    except Exception as e:
        print(f"❌ Company account permission test failed: {e}")
    
    # Test Case 3: PersonalDebt Validation
    print("\n📝 Test 3: PersonalDebt Validation")
    try:
        # Test the new constraints
        from django.db import IntegrityError
        
        # Try to create debt with empty creditor name
        try:
            PersonalDebt.objects.create(
                user=user1,
                creditor_name='',
                principal_amount=Decimal('1000.00'),
                current_balance=Decimal('1000.00'),
                borrowed_date=date.today(),
                due_date=date.today() + timedelta(days=30)
            )
            print("⚠️  Empty creditor name was allowed")
        except IntegrityError:
            print("✅ Empty creditor name properly rejected")
        
        # Try to create debt with invalid date order
        try:
            PersonalDebt.objects.create(
                user=user1,
                creditor_name='Test Creditor',
                principal_amount=Decimal('1000.00'),
                current_balance=Decimal('1000.00'),
                borrowed_date=date.today(),
                due_date=date.today() - timedelta(days=1)  # Due before borrowed
            )
            print("⚠️  Invalid date order was allowed")
        except IntegrityError:
            print("✅ Invalid date order properly rejected")
            
        # Create valid debt
        valid_debt = PersonalDebt.objects.create(
            user=user1,
            creditor_name='Test Valid Creditor',
            principal_amount=Decimal('1000.00'),
            current_balance=Decimal('1000.00'),
            borrowed_date=date.today(),
            due_date=date.today() + timedelta(days=30)
        )
        print("✅ Valid debt created successfully")
        
    except Exception as e:
        print(f"❌ PersonalDebt validation test failed: {e}")
    
    # Test Case 4: Transaction Visibility
    print("\n📝 Test 4: Transaction Visibility")
    try:
        # Create transactions for different accounts (only if accounts exist)
        from finance.views import TransactionViewSet
        
        transaction1 = None
        transaction2 = None
        
        if personal_account1:
            transaction1 = Transaction.objects.create(
                account=personal_account1,
                amount=Decimal('100.00'),
                description='Test transaction 1',
                date=date.today()
            )
        
        if personal_account2:
            transaction2 = Transaction.objects.create(
                account=personal_account2,
                amount=Decimal('200.00'),
                description='Test transaction 2',
                date=date.today()
            )
        
        # Test transaction visibility
        trans_viewset1 = TransactionViewSet()
        trans_viewset1.request = request1
        user1_transactions = trans_viewset1.get_queryset()
        
        trans_viewset2 = TransactionViewSet()
        trans_viewset2.request = request2
        user2_transactions = trans_viewset2.get_queryset()
        
        user1_trans_count = user1_transactions.count()
        user2_trans_count = user2_transactions.count()
        
        print(f"✅ User1 sees {user1_trans_count} transaction(s)")
        print(f"✅ User2 sees {user2_trans_count} transaction(s)")
        
        # Verify transaction isolation (only if both transactions exist)
        if transaction1 and transaction2:
            user1_sees_user2_trans = user1_transactions.filter(id=transaction2.id).exists()
            user2_sees_user1_trans = user2_transactions.filter(id=transaction1.id).exists()
            
            if not user1_sees_user2_trans and not user2_sees_user1_trans:
                print("✅ Transaction visibility isolation working correctly")
            else:
                print("❌ Transaction visibility isolation failed")
        else:
            print("⚠️  Could not test transaction isolation - missing accounts")
            
    except Exception as e:
        print(f"❌ Transaction visibility test failed: {e}")
    
    # Cleanup
    print("\n🧹 Cleaning up test data...")
    try:
        Account.objects.filter(name__startswith='Test').delete()
        PersonalDebt.objects.filter(creditor_name__startswith='Test').delete()
        Permission.objects.filter(name__startswith='Read Company').delete()
        if user2.username == 'testuser2':
            user2.delete()
        print("✅ Cleanup completed")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    print("\n🏁 Account visibility and permission testing completed!")

if __name__ == "__main__":
    test_account_visibility()
