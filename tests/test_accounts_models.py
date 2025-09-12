# tests/test_accounts_models.py
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.models import (
    Department, Designation, Branch, Referral, 
    StaffRole, StaffProfile, CustomerProfile
)
from users.models import User, Tag
from tests.factories import UserFactory


@pytest.mark.django_db
class TestAccountsModels:

    def test_department_creation_and_str(self):
        """Test Department model creation and string representation"""
        dept = Department.objects.create(name="Engineering")
        assert str(dept) == "Engineering"
        assert dept.name == "Engineering"

    def test_designation_creation_and_str(self):
        """Test Designation model creation and string representation"""
        designation = Designation.objects.create(name="Senior Developer")
        assert str(designation) == "Senior Developer"
        assert designation.name == "Senior Developer"

    def test_branch_creation_and_str(self):
        """Test Branch model creation and string representation"""
        branch = Branch.objects.create(name="Kampala Branch")
        assert str(branch) == "Kampala Branch"
        assert branch.name == "Kampala Branch"

    def test_referral_creation_with_unique_code(self):
        """Test Referral model creation with unique code constraint"""
        user = UserFactory()
        referral1 = Referral.objects.create(code="REF001", referrer=user)
        assert referral1.code == "REF001"
        assert referral1.referrer == user
        
        # Test unique constraint
        with pytest.raises(IntegrityError):
            Referral.objects.create(code="REF001", referrer=user)

    def test_referral_without_referrer(self):
        """Test Referral can be created without referrer"""
        referral = Referral.objects.create(code="REF002")
        assert referral.code == "REF002"
        assert referral.referrer is None

    def test_staff_role_creation_and_methods(self):
        """Test StaffRole model creation and methods"""
        tag = Tag.objects.create(label="technical", color="#FF0000")
        
        role = StaffRole.objects.create(
            title="Software Engineer",
            description="Develops software applications",
            dashboard_url="https://dashboard.example.com",
            is_virtual=False,
            prompt_context="You are a helpful software engineer"
        )
        role.tags.add(tag)
        
        assert str(role) == "Software Engineer"
        assert role.title == "Software Engineer"
        assert role.description == "Develops software applications"
        assert role.dashboard_url == "https://dashboard.example.com"
        assert not role.is_virtual
        assert role.prompt_context == "You are a helpful software engineer"
        assert tag in role.tags.all()
        
        # Test BaseModel fields are inherited
        assert hasattr(role, 'created_at')
        assert hasattr(role, 'updated_at')
        assert hasattr(role, 'uuid')

    def test_staff_role_virtual_assistant(self):
        """Test StaffRole as virtual assistant"""
        role = StaffRole.objects.create(
            title="AI Assistant",
            is_virtual=True,
            prompt_context="You are an AI assistant that helps with tasks"
        )
        
        assert role.is_virtual
        assert "ai assistant" in role.prompt_context.lower()

    def test_staff_profile_with_user(self):
        """Test StaffProfile with linked user"""
        user = UserFactory()
        # Delete any existing staff profile for this user
        StaffProfile.objects.filter(user=user).delete()
        
        dept = Department.objects.create(name="IT")
        designation = Designation.objects.create(name="Developer")
        branch = Branch.objects.create(name="Main Branch")
        role = StaffRole.objects.create(title="Engineer")
        assigned_to = UserFactory()
        created_by = UserFactory()
        
        profile = StaffProfile.objects.create(
            user=user,
            department=dept,
            designation=designation,
            branch=branch,
            assigned_to=assigned_to,
            created_by=created_by,
            role=role
        )
        
        assert profile.user == user
        assert profile.department == dept
        assert profile.designation == designation
        assert profile.branch == branch
        assert profile.assigned_to == assigned_to
        assert profile.created_by == created_by
        assert profile.role == role
        
        # Test string representation with user (name is empty, user has no full name, so returns empty string)
        assert str(profile) == ""

    def test_staff_profile_without_user(self):
        """Test StaffProfile without linked user (virtual assistant)"""
        profile = StaffProfile.objects.create(
            name="Virtual Assistant Bot"
        )
        
        assert profile.user is None
        assert profile.name == "Virtual Assistant Bot"
        # The __str__ method returns "[Unlinked Staff]" when user is None, regardless of name
        assert str(profile) == "[Unlinked Staff]"

    def test_staff_profile_unlinked_fallback(self):
        """Test StaffProfile string representation fallback"""
        profile = StaffProfile.objects.create()
        assert str(profile) == "[Unlinked Staff]"

    def test_staff_profile_ordering(self):
        """Test StaffProfile ordering by id"""
        profile1 = StaffProfile.objects.create(name="First")
        profile2 = StaffProfile.objects.create(name="Second")
        
        profiles = list(StaffProfile.objects.all())
        assert profiles[0] == profile1
        assert profiles[1] == profile2

    def test_customer_profile_creation(self):
        """Test CustomerProfile creation and relationships"""
        user = UserFactory()
        referrer = UserFactory()
        referral = Referral.objects.create(code="CUST001", referrer=referrer)
        
        customer = CustomerProfile.objects.create(
            user=user,
            referred_by=referral
        )
        
        assert customer.user == user
        assert customer.referred_by == referral
        assert customer.referred_by.referrer == referrer
        
        # Test BaseModel inheritance
        assert hasattr(customer, 'created_at')
        assert hasattr(customer, 'updated_at')

    def test_customer_profile_without_referral(self):
        """Test CustomerProfile without referral"""
        user = UserFactory()
        customer = CustomerProfile.objects.create(user=user)
        
        assert customer.user == user
        assert customer.referred_by is None

    def test_staff_profile_cascade_relationships(self):
        """Test cascade behavior when related objects are deleted"""
        user = UserFactory()
        # Delete any existing staff profile for this user
        StaffProfile.objects.filter(user=user).delete()
        
        dept = Department.objects.create(name="Test Dept")
        
        profile = StaffProfile.objects.create(
            user=user,
            department=dept
        )
        
        # Delete user should cascade delete profile
        user_id = user.id
        user.delete()
        assert not StaffProfile.objects.filter(user_id=user_id).exists()

    def test_staff_profile_set_null_relationships(self):
        """Test SET_NULL behavior for optional relationships"""
        user = UserFactory()
        # Delete any existing staff profile for this user
        StaffProfile.objects.filter(user=user).delete()
        
        dept = Department.objects.create(name="Test Dept")
        designation = Designation.objects.create(name="Test Role")
        
        profile = StaffProfile.objects.create(
            user=user,
            department=dept,
            designation=designation
        )
        
        # Delete department should set to null
        dept.delete()
        profile.refresh_from_db()
        assert profile.department is None
        assert profile.designation is not None
        
        # Delete designation should set to null
        designation.delete()
        profile.refresh_from_db()
        assert profile.designation is None

    def test_customer_profile_cascade_on_user_delete(self):
        """Test CustomerProfile is deleted when user is deleted"""
        user = UserFactory()
        customer = CustomerProfile.objects.create(user=user)
        customer_id = customer.id
        
        user.delete()
        assert not CustomerProfile.objects.filter(id=customer_id).exists()

    def test_referral_set_null_on_user_delete(self):
        """Test Referral referrer is set to null when user is deleted"""
        user = UserFactory()
        referral = Referral.objects.create(code="TEST001", referrer=user)
        
        user.delete()
        referral.refresh_from_db()
        assert referral.referrer is None
        assert referral.code == "TEST001"  # Referral still exists
