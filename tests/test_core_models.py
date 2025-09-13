# tests/test_core_models.py
import pytest
from django.utils import timezone

from core.models import BaseModel, SingletonBaseModel
from accounts.models import StaffRole  # Use existing model that inherits BaseModel


@pytest.mark.django_db
class TestCoreModels:

    def test_base_model_fields(self):
        """Test BaseModel provides all expected fields"""
        obj = StaffRole.objects.create(title="Test Role")
        
        # Check all BaseModel fields exist
        assert hasattr(obj, 'created_at')
        assert hasattr(obj, 'updated_at')
        assert hasattr(obj, 'deleted_at')
        assert hasattr(obj, 'is_deleted')
        assert hasattr(obj, 'uuid')
        
        # Check field values
        assert obj.created_at is not None
        assert obj.updated_at is not None
        assert obj.deleted_at is None
        assert obj.is_deleted is False
        assert obj.uuid is not None

    def test_base_model_auto_timestamps(self):
        """Test BaseModel automatically sets timestamps"""
        before_create = timezone.now()
        obj = StaffRole.objects.create(title="Timestamp Test")
        after_create = timezone.now()
        
        # created_at should be between before and after
        assert before_create <= obj.created_at <= after_create
        assert before_create <= obj.updated_at <= after_create
        
        # Update the object
        original_created = obj.created_at
        original_updated = obj.updated_at
        
        obj.title = "Updated Title"
        before_update = timezone.now()
        obj.save()
        after_update = timezone.now()
        
        # created_at should not change, updated_at should change
        assert obj.created_at == original_created
        assert before_update <= obj.updated_at <= after_update
        assert obj.updated_at > original_updated

    def test_base_model_uuid_unique(self):
        """Test BaseModel UUID field is unique for each instance"""
        obj1 = StaffRole.objects.create(title="Object 1")
        obj2 = StaffRole.objects.create(title="Object 2")
        
        assert obj1.uuid != obj2.uuid
        assert obj1.uuid is not None
        assert obj2.uuid is not None

    def test_base_model_soft_delete(self):
        """Test BaseModel soft delete functionality"""
        obj = StaffRole.objects.create(title="To Delete")
        
        # Initially not deleted
        assert not obj.is_deleted
        assert obj.deleted_at is None
        
        # Perform soft delete
        before_delete = timezone.now()
        obj.soft_delete()
        after_delete = timezone.now()
        
        # Check soft delete worked
        assert obj.is_deleted is True
        assert before_delete <= obj.deleted_at <= after_delete

    def test_staff_role_inherits_base_model(self):
        """Test StaffRole inherits BaseModel functionality"""
        obj = StaffRole.objects.create(title="Test Role")
        
        # Should have all BaseModel fields
        assert hasattr(obj, 'created_at')
        assert hasattr(obj, 'updated_at')
        assert hasattr(obj, 'deleted_at')
        assert hasattr(obj, 'is_deleted')
        assert hasattr(obj, 'uuid')
        
        # Should have soft_delete method
        assert hasattr(obj, 'soft_delete')
        
        # Test soft delete works
        obj.soft_delete()
        assert obj.is_deleted is True
        assert obj.deleted_at is not None

    def test_base_model_is_abstract(self):
        """Test BaseModel is abstract and cannot be instantiated directly"""
        # BaseModel should be abstract
        assert BaseModel._meta.abstract is True

    def test_singleton_base_model_is_abstract(self):
        """Test SingletonBaseModel is abstract"""
        assert SingletonBaseModel._meta.abstract is True

    def test_base_model_ordering_not_specified(self):
        """Test BaseModel doesn't specify default ordering"""
        # BaseModel shouldn't have default ordering
        assert not hasattr(BaseModel._meta, 'ordering') or BaseModel._meta.ordering == []

    def test_multiple_department_instances_different_pks(self):
        """Test multiple Department instances have different primary keys"""
        obj1 = StaffRole.objects.create(title="Department 1")
        obj2 = StaffRole.objects.create(title="Department 2")
        
        # Should have different primary keys
        assert obj1.pk != obj2.pk
        
        # Both should exist in database
        assert StaffRole.objects.count() >= 2

    def test_base_model_deleted_at_null_by_default(self):
        """Test deleted_at is null by default and is_deleted is False"""
        obj = StaffRole.objects.create(title="Default State Test")
        
        assert obj.deleted_at is None
        assert obj.is_deleted is False

    def test_soft_delete_sets_both_fields(self):
        """Test soft_delete sets both deleted_at and is_deleted"""
        obj = StaffRole.objects.create(title="Soft Delete Test")
        
        # Before soft delete
        assert obj.deleted_at is None
        assert obj.is_deleted is False
        
        # After soft delete
        obj.soft_delete()
        assert obj.deleted_at is not None
        assert obj.is_deleted is True
        
        # Verify it was saved to database
        obj.refresh_from_db()
        assert obj.deleted_at is not None
        assert obj.is_deleted is True
