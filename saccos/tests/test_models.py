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


class SaccoOrganizationTests(TestCase):
    """Tests for SaccoOrganization model - Phase 1"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='pass123',
            email='admin@test.com'
        )
    
    def test_create_sacco_organization(self):
        """Test creating a SACCO organization"""
        sacco = SaccoOrganization.objects.create(
            name="Test SACCO",
            registration_number="TS001",
            email="test@sacco.com",
            phone="0700000000",
            cash_round_amount=Decimal('51000')
        )
        
        self.assertEqual(sacco.name, "Test SACCO")
        self.assertEqual(sacco.registration_number, "TS001")
        self.assertTrue(sacco.is_active)
        self.assertEqual(sacco.member_count, 0)
    
    def test_sacco_member_count(self):
        """Test member count property"""
        sacco = SaccoOrganization.objects.create(name="Test SACCO")
        self.assertEqual(sacco.member_count, 0)
        
        # Create members
        for i in range(5):
            user = User.objects.create_user(
                username=f'member{i}',
                password='pass123'
            )
            SaccoMember.objects.create(
                user=user,
                sacco=sacco,
                member_number=f'M00{i+1}',
                status='active'
            )
        
        self.assertEqual(sacco.member_count, 5)
    
    def test_subscription_active(self):
        """Test subscription status checking"""
        sacco = SaccoOrganization.objects.create(
            name="Test SACCO",
            subscription_status='active'
        )
        self.assertTrue(sacco.is_subscription_active())
        
        sacco.subscription_status = 'trial'
        sacco.save()
        self.assertFalse(sacco.is_subscription_active())


class SaccoMemberTests(TestCase):
    """Tests for SaccoMember model - Phase 1"""
    
    def setUp(self):
        self.sacco = SaccoOrganization.objects.create(name="Test SACCO")
        self.user = User.objects.create_user(
            username='member1',
            password='pass123'
        )
    
    def test_create_sacco_member(self):
        """Test creating a SACCO member"""
        member = SaccoMember.objects.create(
            user=self.user,
            sacco=self.sacco,
            member_number='M001',
            passbook_number='PB001',
            status='active'
        )
        
        self.assertEqual(member.member_number, 'M001')
        self.assertEqual(member.status, 'active')
        self.assertEqual(member.sacco, self.sacco)
    
    def test_member_get_passbook(self):
        """Test getting or creating member passbook"""
        member = SaccoMember.objects.create(
            user=self.user,
            sacco=self.sacco,
            member_number='M001'
        )
        
        # First call should create passbook
        passbook = member.get_passbook()
        self.assertIsNotNone(passbook)
        self.assertEqual(passbook.member, member)
        
        # Second call should return same passbook
        passbook2 = member.get_passbook()
        self.assertEqual(passbook.id, passbook2.id)
    
    def test_member_roles(self):
        """Test member role flags"""
        member = SaccoMember.objects.create(
            user=self.user,
            sacco=self.sacco,
            member_number='M001',
            is_secretary=True
        )
        
        self.assertTrue(member.is_secretary)
        self.assertFalse(member.is_treasurer)
        self.assertFalse(member.is_chairperson)


class PassbookSectionTests(TestCase):
    """Tests for PassbookSection model - Phase 2"""
    
    def setUp(self):
        self.sacco = SaccoOrganization.objects.create(name="Test SACCO")
    
    def test_create_passbook_section(self):
        """Test creating a passbook section"""
        section = PassbookSection.objects.create(
            sacco=self.sacco,
            name="Compulsory Savings",
            section_type='savings',
            is_compulsory=True,
            weekly_amount=Decimal('2000')
        )
        
        self.assertEqual(section.name, "Compulsory Savings")
        self.assertTrue(section.is_compulsory)
        self.assertEqual(section.weekly_amount, Decimal('2000'))
    
    def test_create_default_sections(self):
        """Test creating default sections for a SACCO"""
        sections = PassbookSection.create_default_sections(self.sacco)
        
        self.assertEqual(len(sections), 7)
        section_names = [s.name for s in sections]
        self.assertIn('Compulsory Savings', section_names)
        self.assertIn('Welfare', section_names)
        self.assertIn('Development', section_names)
        self.assertIn('Loan', section_names)


class PassbookEntryTests(TestCase):
    """Tests for PassbookEntry model - Phase 2"""
    
    def setUp(self):
        self.sacco = SaccoOrganization.objects.create(name="Test SACCO")
        self.user = User.objects.create_user(username='member1', password='pass123')
        self.member = SaccoMember.objects.create(
            user=self.user,
            sacco=self.sacco,
            member_number='M001'
        )
        self.passbook = self.member.get_passbook()
        self.section = PassbookSection.objects.create(
            sacco=self.sacco,
            name="Savings",
            section_type='savings'
        )
        self.recorder = User.objects.create_user(username='secretary', password='pass123')
    
    def test_create_passbook_entry_credit(self):
        """Test creating a credit entry"""
        entry = PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='credit',
            amount=Decimal('5000'),
            description='Weekly savings',
            recorded_by=self.recorder
        )
        
        self.assertEqual(entry.amount, Decimal('5000'))
        self.assertEqual(entry.balance_after, Decimal('5000'))
        self.assertEqual(entry.transaction_type, 'credit')
    
    def test_running_balance_calculation(self):
        """Test that running balance is calculated correctly"""
        # First entry
        entry1 = PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='credit',
            amount=Decimal('3000'),
            description='Payment 1',
            recorded_by=self.recorder
        )
        self.assertEqual(entry1.balance_after, Decimal('3000'))
        
        # Second entry
        entry2 = PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='credit',
            amount=Decimal('2000'),
            description='Payment 2',
            recorded_by=self.recorder
        )
        self.assertEqual(entry2.balance_after, Decimal('5000'))
        
        # Debit entry
        entry3 = PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='debit',
            amount=Decimal('1000'),
            description='Withdrawal',
            recorded_by=self.recorder
        )
        self.assertEqual(entry3.balance_after, Decimal('4000'))
    
    def test_passbook_get_section_balance(self):
        """Test getting current balance for a section"""
        # Create multiple entries
        PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='credit',
            amount=Decimal('5000'),
            description='Payment 1',
            recorded_by=self.recorder
        )
        
        PassbookEntry.objects.create(
            passbook=self.passbook,
            section=self.section,
            transaction_date=timezone.now().date(),
            transaction_type='credit',
            amount=Decimal('3000'),
            description='Payment 2',
            recorded_by=self.recorder
        )
        
        balance = self.passbook.get_section_balance(self.section)
        self.assertEqual(balance, Decimal('8000'))


class DeductionRuleTests(TestCase):
    """Tests for DeductionRule model - Phase 2"""
    
    def setUp(self):
        self.sacco = SaccoOrganization.objects.create(name="Test SACCO")
        self.section = PassbookSection.objects.create(
            sacco=self.sacco,
            name="Welfare",
            section_type='welfare'
        )
    
    def test_create_deduction_rule(self):
        """Test creating a deduction rule"""
        rule = DeductionRule.objects.create(
            sacco=self.sacco,
            section=self.section,
            amount=Decimal('5000'),
            applies_to='recipient',
            is_active=True,
            effective_from=timezone.now().date()
        )
        
        self.assertEqual(rule.amount, Decimal('5000'))
        self.assertEqual(rule.applies_to, 'recipient')
        self.assertTrue(rule.is_active)
    
    def test_deduction_rule_is_effective(self):
        """Test checking if rule is effective on a given date"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        rule = DeductionRule.objects.create(
            sacco=self.sacco,
            section=self.section,
            amount=Decimal('5000'),
            is_active=True,
            effective_from=today,
            effective_until=tomorrow
        )
        
        # Should be effective today
        self.assertTrue(rule.is_effective(today))
        
        # Should not be effective yesterday
        self.assertFalse(rule.is_effective(yesterday))
        
        # Should be effective tomorrow (on the last day)
        self.assertTrue(rule.is_effective(tomorrow))
        
        # Should not be effective day after tomorrow
        day_after = tomorrow + timedelta(days=1)
        self.assertFalse(rule.is_effective(day_after))
