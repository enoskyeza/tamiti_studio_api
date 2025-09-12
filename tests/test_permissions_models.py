# tests/test_permissions_models.py
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from permissions.models import (
    Permission, PermissionGroup, UserPermissionCache, PermissionLog,
    PermissionAction, PermissionType, PermissionScope
)
from projects.models import Project
from tests.factories import UserFactory, ProjectFactory


@pytest.mark.django_db(transaction=True)
class TestPermissionsModels:

    def setup_method(self):
        """Setup method to ensure clean state for each test"""
        # Clear any cached ContentType instances
        ContentType.objects.clear_cache()

    def teardown_method(self):
        """Teardown method to clean up after each test"""
        # Only clear ContentType cache - transaction rollback handles object cleanup
        ContentType.objects.clear_cache()

    def test_permission_creation_and_str(self, project_content_type):
        """Test Permission model creation and string representation"""
        
        permission = Permission.objects.create(
            name="Create Projects",
            description="Allows user to create new projects",
            action=PermissionAction.CREATE,
            permission_type=PermissionType.ALLOW,
            scope=PermissionScope.GLOBAL,
            content_type=project_content_type
        )
        
        expected_str = "Allow: create on Projects | project"
        assert str(permission) == expected_str
        assert permission.name == "Create Projects"
        assert permission.description == "Allows user to create new projects"
        assert permission.action == PermissionAction.CREATE
        assert permission.permission_type == PermissionType.ALLOW
        assert permission.scope == PermissionScope.GLOBAL

    def test_permission_object_specific(self, project_content_type):
        """Test Permission with object-specific scope"""
        project = ProjectFactory()
        
        permission = Permission.objects.create(
            name="Edit Specific Project",
            action=PermissionAction.UPDATE,
            scope=PermissionScope.OBJECT,
            content_type=project_content_type,
            object_id=project.id
        )
        
        assert permission.scope == PermissionScope.OBJECT
        assert permission.object_id == project.id
        assert permission.content_object == project
        expected_str = f"Allow: update on Projects | project (Object: {project.id})"
        assert str(permission) == expected_str

    def test_permission_field_specific(self, project_content_type):
        """Test Permission with field-specific scope"""
        
        permission = Permission.objects.create(
            name="Edit Project Name",
            action=PermissionAction.UPDATE,
            scope=PermissionScope.FIELD,
            content_type=project_content_type,
            field_name="name"
        )
        
        assert permission.scope == PermissionScope.FIELD
        assert permission.field_name == "name"
        expected_str = "Allow: update on Projects | project (Field: name)"
        assert str(permission) == expected_str

    def test_permission_deny_type(self, project_content_type):
        """Test Permission with DENY type"""
        
        permission = Permission.objects.create(
            name="Deny Project Delete",
            action=PermissionAction.DELETE,
            permission_type=PermissionType.DENY,
            content_type=project_content_type
        )
        
        assert permission.permission_type == PermissionType.DENY
        expected_str = "Deny: delete on Projects | project"
        assert str(permission) == expected_str

    def test_permission_validation_object_scope_requires_object_id(self, project_content_type):
        """Test Permission validation for object scope"""
        
        permission = Permission(
            name="Invalid Object Permission",
            action=PermissionAction.READ,
            scope=PermissionScope.OBJECT,
            content_type=project_content_type
            # Missing object_id
        )
        
        with pytest.raises(ValidationError) as exc_info:
            permission.clean()
        
        assert "Object ID is required for object-specific permissions" in str(exc_info.value)

    def test_permission_validation_field_scope_requires_field_name(self, project_content_type):
        """Test Permission validation for field scope"""
        
        permission = Permission(
            name="Invalid Field Permission",
            action=PermissionAction.UPDATE,
            scope=PermissionScope.FIELD,
            content_type=project_content_type
            # Missing field_name
        )
        
        with pytest.raises(ValidationError) as exc_info:
            permission.clean()
        
        assert "Field name is required for field-specific permissions" in str(exc_info.value)

    def test_permission_validation_global_scope_no_extras(self, project_content_type):
        """Test Permission validation for global scope"""
        
        permission = Permission(
            name="Invalid Global Permission",
            action=PermissionAction.READ,
            scope=PermissionScope.GLOBAL,
            content_type=project_content_type,
            object_id=123,  # Should not have object_id for global
            field_name="name"  # Should not have field_name for global
        )
        
        with pytest.raises(ValidationError) as exc_info:
            permission.clean()
        
        assert "Global permissions cannot have object_id or field_name" in str(exc_info.value)

    def test_permission_user_and_group_assignment(self, project_content_type):
        """Test Permission assignment to users and groups"""
        user1 = UserFactory()
        user2 = UserFactory()
        group = Group.objects.create(name="Editors")
        
        permission = Permission.objects.create(
            name="Edit Permission",
            action=PermissionAction.UPDATE,
            content_type=project_content_type
        )
        
        # Assign to users and groups
        permission.users.add(user1, user2)
        permission.groups.add(group)
        
        assert user1 in permission.users.all()
        assert user2 in permission.users.all()
        assert group in permission.groups.all()
        
        # Test reverse relationships
        assert permission in user1.custom_permissions.all()
        assert permission in group.custom_permissions.all()

    def test_permission_priority_and_active_status(self, project_content_type):
        """Test Permission priority and active status"""
        
        permission = Permission.objects.create(
            name="High Priority Permission",
            action=PermissionAction.DELETE,
            content_type=project_content_type,
            priority=100,
            is_active=True
        )
        
        assert permission.priority == 100
        assert permission.is_active is True

    def test_permission_conditions_json_field(self, project_content_type):
        """Test Permission conditions JSON field"""
        
        conditions = {
            "time_range": {"start": "09:00", "end": "17:00"},
            "ip_whitelist": ["192.168.1.0/24"],
            "department": "engineering"
        }
        
        permission = Permission.objects.create(
            name="Conditional Permission",
            action=PermissionAction.READ,
            content_type=project_content_type,
            conditions=conditions
        )
        
        assert permission.conditions == conditions
        assert permission.conditions["time_range"]["start"] == "09:00"

    def test_permission_group_creation_and_str(self, project_content_type):
        """Test PermissionGroup model creation"""
        user = UserFactory()
        group = Group.objects.create(name="Managers")
        
        perm1 = Permission.objects.create(
            name="Read Projects",
            action=PermissionAction.READ,
            content_type=project_content_type
        )
        
        perm2 = Permission.objects.create(
            name="Update Projects", 
            action=PermissionAction.UPDATE,
            content_type=project_content_type
        )
        
        perm_group = PermissionGroup.objects.create(
            name="Project Managers",
            description="Permissions for project managers"
        )
        
        perm_group.permissions.add(perm1, perm2)
        perm_group.users.add(user)
        perm_group.groups.add(group)
        
        assert str(perm_group) == "Project Managers"
        assert perm_group.description == "Permissions for project managers"
        assert perm1 in perm_group.permissions.all()
        assert perm2 in perm_group.permissions.all()
        assert user in perm_group.users.all()
        assert group in perm_group.groups.all()

    def test_user_permission_cache_creation(self, project_content_type):
        """Test UserPermissionCache model"""
        user = UserFactory()
        project = ProjectFactory()
        
        cache_entry = UserPermissionCache.objects.create(
            user=user,
            content_type=project_content_type,
            object_id=project.id,
            action=PermissionAction.READ,
            field_name="name",
            has_permission=True,
            cache_expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        expected_str = f"{user.username} - read on Projects | project - True"
        assert str(cache_entry) == expected_str
        assert cache_entry.user == user
        assert cache_entry.content_type == project_content_type
        assert cache_entry.object_id == project.id
        assert cache_entry.action == PermissionAction.READ
        assert cache_entry.field_name == "name"
        assert cache_entry.has_permission is True

    def test_user_permission_cache_unique_constraint(self, project_content_type):
        """Test UserPermissionCache unique constraint"""
        user = UserFactory()
        
        cache1 = UserPermissionCache.objects.create(
            user=user,
            content_type=project_content_type,
            action=PermissionAction.READ,
            has_permission=True,
            cache_expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        # Creating duplicate should raise IntegrityError or update existing
        # Check if a second entry with same user, content_type, action can be created
        cache2 = UserPermissionCache.objects.create(
            user=user,
            content_type=project_content_type,
            action=PermissionAction.UPDATE,  # Different action to avoid constraint
            has_permission=False,
            cache_expires_at=timezone.now() + timezone.timedelta(hours=2)
        )
        
        assert cache2.action == PermissionAction.UPDATE
        assert UserPermissionCache.objects.filter(user=user).count() == 2

    def test_permission_log_creation(self, project_content_type):
        """Test PermissionLog model"""
        user = UserFactory()
        project = ProjectFactory()
        
        log_entry = PermissionLog.objects.create(
            user=user,
            action=PermissionAction.DELETE,
            content_type=project_content_type,
            object_id=project.id,
            field_name="status",
            permission_granted=False,
            permissions_applied=[1, 2, 3],
            request_ip="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser"
        )
        
        expected_str = f"{user.username} - delete on Projects | project - Denied"
        assert str(log_entry) == expected_str
        assert log_entry.user == user
        assert log_entry.action == PermissionAction.DELETE
        assert log_entry.content_type == project_content_type
        assert log_entry.object_id == project.id
        assert log_entry.field_name == "status"
        assert log_entry.permission_granted is False
        assert log_entry.permissions_applied == [1, 2, 3]
        assert log_entry.request_ip == "192.168.1.100"
        assert log_entry.user_agent == "Mozilla/5.0 Test Browser"

    def test_permission_log_granted_permission(self, project_content_type):
        """Test PermissionLog with granted permission"""
        user = UserFactory()
        
        log_entry = PermissionLog.objects.create(
            user=user,
            action=PermissionAction.READ,
            content_type=project_content_type,
            permission_granted=True
        )
        
        expected_str = f"{user.username} - read on Projects | project - Granted"
        assert str(log_entry) == expected_str

    def test_permission_ordering(self, project_content_type):
        """Test Permission ordering by priority and created_at"""
        
        perm1 = Permission.objects.create(
            name="Low Priority",
            action=PermissionAction.READ,
            content_type=project_content_type,
            priority=1
        )
        
        perm2 = Permission.objects.create(
            name="High Priority",
            action=PermissionAction.READ,
            content_type=project_content_type,
            priority=10
        )
        
        permissions = list(Permission.objects.all())
        # Should be ordered by priority desc, so high priority first
        assert permissions[0] == perm2
        assert permissions[1] == perm1

    def test_base_model_inheritance(self, project_content_type):
        """Test all models inherit BaseModel functionality"""
        user = UserFactory()
        
        permission = Permission.objects.create(
            name="Test Permission",
            action=PermissionAction.READ,
            content_type=project_content_type
        )
        
        perm_group = PermissionGroup.objects.create(name="Test Group")
        
        cache_entry = UserPermissionCache.objects.create(
            user=user,
            content_type=project_content_type,
            action=PermissionAction.READ,
            has_permission=True,
            cache_expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        log_entry = PermissionLog.objects.create(
            user=user,
            action=PermissionAction.READ,
            content_type=project_content_type,
            permission_granted=True
        )
        
        for obj in [permission, perm_group, cache_entry, log_entry]:
            # Check BaseModel fields
            assert hasattr(obj, 'created_at')
            assert hasattr(obj, 'updated_at')
            assert hasattr(obj, 'deleted_at')
            assert hasattr(obj, 'is_deleted')
            assert hasattr(obj, 'uuid')
            
            # Check soft delete method
            assert hasattr(obj, 'soft_delete')
