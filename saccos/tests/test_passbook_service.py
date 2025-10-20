from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from users.models import User
from saccos.models import (
    SaccoOrganization,
    SaccoMember,
    MemberPassbook,
    PassbookSection,
    PassbookEntry,
    DeductionRule
)
from saccos.services.passbook_service import PassbookService


class PassbookServiceTests(TestCase):
    """Tests for PassbookService - Phase 2"""
    
    def setUp(self):
        # Create SACCO and member
        self.sacco = SaccoOrganization.objects.create(name="Test SACCO")
        PassbookSection.create_default_sections(self.sacco)
        
        # Create test user and member
        self.user = User.objects.create_user(
            username='testmember',
            password='pass123'
        )
        self.member = SaccoMember.objects.create(
            user=self.user,
            sacco=self.sacco,
            member_number='M001'
        )
        self.passbook = PassbookService.create_passbook(self.member)
        
        # Create recorder
        self.recorder = User.objects.create_user(
            username='secretary',
            password='pass123'
        )
    
    def test_create_passbook(self):
        """Test creating a passbook for a member"""
        user2 = User.objects.create_user(username='member2', password='pass123')
        member2 = SaccoMember.objects.create(
            user=user2,
            sacco=self.sacco,
            member_number='M002'
        )
        
        passbook = PassbookService.create_passbook(member2)
        
        self.assertIsNotNone(passbook)
        self.assertEqual(passbook.member, member2)
        self.assertEqual(passbook.sacco, self.sacco)
        self.assertEqual(passbook.passbook_number, 'M002')
    
    def test_record_entry(self):
        """Test recording a passbook entry"""
        section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Compulsory Savings'
        )
        
        entry = PassbookService.record_entry(
            passbook=self.passbook,
            section=section,
            amount=Decimal('5000'),
            transaction_type='credit',
            description='Weekly savings',
            recorded_by=self.recorder
        )
        
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, Decimal('5000'))
        self.assertEqual(entry.balance_after, Decimal('5000'))
        self.assertEqual(entry.recorded_by, self.recorder)
    
    def test_get_section_balance(self):
        """Test getting current balance for a section"""
        section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Welfare'
        )
        
        # Record multiple entries
        PassbookService.record_entry(
            self.passbook, section, Decimal('3000'),
            'credit', 'Payment 1', self.recorder
        )
        PassbookService.record_entry(
            self.passbook, section, Decimal('2000'),
            'credit', 'Payment 2', self.recorder
        )
        PassbookService.record_entry(
            self.passbook, section, Decimal('1000'),
            'debit', 'Withdrawal', self.recorder
        )
        
        balance = PassbookService.get_section_balance(self.passbook, section)
        self.assertEqual(balance, Decimal('4000'))
    
    def test_get_all_balances(self):
        """Test getting balances for all sections"""
        # Record entries in multiple sections
        savings_section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Compulsory Savings'
        )
        welfare_section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Welfare'
        )
        
        PassbookService.record_entry(
            self.passbook, savings_section, Decimal('2000'),
            'credit', 'Savings', self.recorder
        )
        PassbookService.record_entry(
            self.passbook, welfare_section, Decimal('5000'),
            'credit', 'Welfare', self.recorder
        )
        
        balances = PassbookService.get_all_balances(self.passbook)
        
        self.assertIn('Compulsory Savings', balances)
        self.assertIn('Welfare', balances)
        self.assertEqual(balances['Compulsory Savings']['balance'], Decimal('2000'))
        self.assertEqual(balances['Welfare']['balance'], Decimal('5000'))
    
    def test_generate_statement(self):
        """Test generating a passbook statement"""
        section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Compulsory Savings'
        )
        
        # Record entries over time
        today = timezone.now().date()
        
        for i in range(5):
            PassbookService.record_entry(
                passbook=self.passbook,
                section=section,
                amount=Decimal('1000'),
                transaction_type='credit',
                description=f'Payment {i+1}',
                recorded_by=self.recorder,
                transaction_date=today - timedelta(days=i)
            )
        
        # Generate statement
        statement = PassbookService.generate_statement(
            passbook=self.passbook,
            start_date=today - timedelta(days=30),
            end_date=today
        )
        
        self.assertIn('member', statement)
        self.assertIn('period', statement)
        self.assertIn('sections', statement)
        self.assertIn('summary', statement)
        
        self.assertEqual(statement['member']['member_number'], 'M001')
        self.assertEqual(statement['summary']['total_credits'], Decimal('5000'))
    
    def test_generate_statement_for_specific_section(self):
        """Test generating statement for a specific section"""
        section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Compulsory Savings'
        )
        other_section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Welfare'
        )
        
        # Record in both sections
        PassbookService.record_entry(
            self.passbook, section, Decimal('2000'),
            'credit', 'Savings', self.recorder
        )
        PassbookService.record_entry(
            self.passbook, other_section, Decimal('5000'),
            'credit', 'Welfare', self.recorder
        )
        
        # Generate statement for savings only
        statement = PassbookService.generate_statement(
            passbook=self.passbook,
            section=section
        )
        
        self.assertEqual(len(statement['sections']), 1)
        self.assertEqual(statement['sections'][0]['section']['name'], 'Compulsory Savings')
    
    def test_get_compulsory_deductions(self):
        """Test getting compulsory deduction rules"""
        # Create deduction rules
        welfare_section = PassbookSection.objects.get(
            sacco=self.sacco,
            section_type='welfare'
        )
        dev_section = PassbookSection.objects.get(
            sacco=self.sacco,
            section_type='development'
        )
        
        today = timezone.now().date()
        
        DeductionRule.objects.create(
            sacco=self.sacco,
            section=welfare_section,
            amount=Decimal('5000'),
            applies_to='recipient',
            is_active=True,
            effective_from=today
        )
        
        DeductionRule.objects.create(
            sacco=self.sacco,
            section=dev_section,
            amount=Decimal('5000'),
            applies_to='recipient',
            is_active=True,
            effective_from=today
        )
        
        rules = PassbookService.get_compulsory_deductions(self.sacco, today)
        
        self.assertEqual(len(rules), 2)
        total_deductions = sum(r.amount for r in rules)
        self.assertEqual(total_deductions, Decimal('10000'))
    
    def test_reverse_entry(self):
        """Test reversing a passbook entry"""
        section = PassbookSection.objects.get(
            sacco=self.sacco,
            name='Compulsory Savings'
        )
        
        # Create original entry
        entry = PassbookService.record_entry(
            passbook=self.passbook,
            section=section,
            amount=Decimal('5000'),
            transaction_type='credit',
            description='Original payment',
            recorded_by=self.recorder
        )
        
        # Reverse it
        reversal = PassbookService.reverse_entry(
            entry=entry,
            recorded_by=self.recorder,
            reason='Payment error'
        )
        
        self.assertTrue(reversal.is_reversal)
        self.assertEqual(reversal.reverses_entry, entry)
        self.assertEqual(reversal.amount, Decimal('5000'))
        self.assertEqual(reversal.transaction_type, 'debit')
        self.assertIn('REVERSAL', reversal.description)
        
        # Balance should be back to zero
        balance = PassbookService.get_section_balance(self.passbook, section)
        self.assertEqual(balance, Decimal('0'))
