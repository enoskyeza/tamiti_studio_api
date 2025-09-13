#!/usr/bin/env python
"""
Local test script to identify debt creation issues
Run this to test debt creation locally before investigating server logs
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
from finance.models import PersonalDebt
from finance.services import PersonalFinanceService

User = get_user_model()

def test_debt_creation():
    """Test various debt creation scenarios to identify potential issues"""
    
    print("🔍 Testing PersonalDebt creation scenarios...")
    
    # Get or create a test user
    try:
        user = User.objects.first()
        if not user:
            print("❌ No users found. Create a user first.")
            return
        print(f"✅ Using user: {user.username}")
    except Exception as e:
        print(f"❌ Error getting user: {e}")
        return
    
    # Test Case 1: Basic debt creation
    print("\n📝 Test 1: Basic debt creation")
    try:
        debt_data = {
            'creditor_name': 'Test Creditor',
            'creditor_contact': '+256700000000',
            'principal_amount': '1000.00',
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'description': 'Test debt'
        }
        
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"✅ Basic debt created: ID {debt.id}")
        debt.delete()  # Cleanup
        
    except Exception as e:
        print(f"❌ Basic debt creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    # Test Case 2: Debt with interest
    print("\n📝 Test 2: Debt with interest")
    try:
        debt_data = {
            'creditor_name': 'Bank Loan',
            'principal_amount': '5000.00',
            'current_balance': '5000.00',
            'interest_rate': '15.5',
            'has_interest': True,
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=365),
        }
        
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"✅ Interest debt created: ID {debt.id}")
        debt.delete()  # Cleanup
        
    except Exception as e:
        print(f"❌ Interest debt creation failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    # Test Case 3: Invalid data scenarios
    print("\n📝 Test 3: Invalid data scenarios")
    
    # Missing required fields
    try:
        debt_data = {
            'creditor_name': '',  # Empty name
            'principal_amount': '1000.00',
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
        }
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"⚠️  Empty creditor name allowed: ID {debt.id}")
        debt.delete()
    except Exception as e:
        print(f"✅ Empty creditor name properly rejected: {e}")
    
    # Negative amount
    try:
        debt_data = {
            'creditor_name': 'Test Creditor',
            'principal_amount': '-1000.00',  # Negative amount
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
        }
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"⚠️  Negative amount allowed: ID {debt.id}")
        debt.delete()
    except Exception as e:
        print(f"✅ Negative amount properly rejected: {e}")
    
    # Invalid date order
    try:
        debt_data = {
            'creditor_name': 'Test Creditor',
            'principal_amount': '1000.00',
            'borrowed_date': date.today(),
            'due_date': date.today() - timedelta(days=30),  # Due date before borrowed date
        }
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"⚠️  Invalid date order allowed: ID {debt.id}")
        debt.delete()
    except Exception as e:
        print(f"✅ Invalid date order properly rejected: {e}")
    
    # Test Case 4: Decimal precision issues
    print("\n📝 Test 4: Decimal precision scenarios")
    try:
        debt_data = {
            'creditor_name': 'Precision Test',
            'principal_amount': '1000.123456789',  # High precision
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
        }
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"✅ High precision amount handled: {debt.principal_amount}")
        debt.delete()
    except Exception as e:
        print(f"❌ Decimal precision error: {e}")
    
    # Test Case 5: Unicode/Special characters
    print("\n📝 Test 5: Unicode and special characters")
    try:
        debt_data = {
            'creditor_name': 'Müller & Co. (Zürich) 🏦',  # Unicode characters
            'creditor_contact': '+41-44-123-45-67',
            'principal_amount': '1000.00',
            'borrowed_date': date.today(),
            'due_date': date.today() + timedelta(days=30),
            'description': 'Loan with émojis and spëcial chàracters 💰'
        }
        debt = PersonalFinanceService.create_personal_debt(user, debt_data)
        print(f"✅ Unicode characters handled: ID {debt.id}")
        debt.delete()
    except Exception as e:
        print(f"❌ Unicode character error: {e}")
    
    print("\n🏁 Debt creation testing completed!")

if __name__ == "__main__":
    test_debt_creation()
