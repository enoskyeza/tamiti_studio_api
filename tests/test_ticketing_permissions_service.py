# tests/test_ticketing_permissions_service.py
"""
Test ticketing permission service and batch permission checking
"""
import pytest
from tests.factories import (
    UserFactory, EventFactory, EventMembershipFactory, BatchFactory, 
    BatchMembershipFactory, TicketTypeFactory
)
from ticketing.views import BatchViewSet


@pytest.mark.django_db(transaction=True)
class TestBatchPermissionService:
    """Test batch permission checking logic"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.manager = UserFactory()
        self.batch_manager = UserFactory()
        self.outsider = UserFactory()
        self.staff = UserFactory(is_staff=True)
        
        self.event = EventFactory(created_by=self.owner)
        self.ticket_type = TicketTypeFactory(event=self.event, created_by=self.owner)
        self.batch = BatchFactory(
            event=self.event,
            ticket_type=self.ticket_type,
            created_by=self.owner
        )
        
        # Create event membership with various permissions
        self.event_membership = EventMembershipFactory(
            event=self.event,
            user=self.manager,
            permissions={
                'activate_tickets': True,
                'verify_tickets': True,
                'void_batches': True,
                'create_batches': True
            },
            invited_by=self.owner
        )
        
        # Create batch membership
        self.batch_membership = BatchMembershipFactory(
            batch=self.batch,
            membership=self.event_membership,
            can_activate=True,
            can_verify=False,  # Note: can't verify at batch level
            assigned_by=self.owner
        )
        
        # Create a batch viewset instance for testing
        self.batch_viewset = BatchViewSet()
    
    def test_staff_has_all_permissions(self):
        """Test that staff users have all permissions"""
        assert self.batch_viewset.check_batch_permission(self.batch, self.staff) is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.staff, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.staff, 'can_verify') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.staff, 'void_batches') is True
    
    def test_event_owner_has_all_permissions(self):
        """Test that event owners have all permissions"""
        assert self.batch_viewset.check_batch_permission(self.batch, self.owner) is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.owner, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.owner, 'can_verify') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.owner, 'void_batches') is True
    
    def test_event_manager_permissions(self):
        """Test event manager permissions based on their permission dict"""
        # Manager has activate_tickets permission
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'can_activate') is True
        
        # Manager has verify_tickets permission
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'can_verify') is True
        
        # Manager has void_batches permission
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'void_batches') is True
        
        # Manager has create_batches permission
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'create_batches') is True
        
        # Basic access should be granted
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager) is True
    
    def test_event_manager_without_specific_permission(self):
        """Test event manager without specific permissions"""
        # Create manager without void permission
        limited_manager = UserFactory()
        EventMembershipFactory(
            event=self.event,
            user=limited_manager,
            permissions={
                'activate_tickets': True,
                'verify_tickets': False,  # No verify permission
                'void_batches': False,    # No void permission
            },
            invited_by=self.owner
        )
        
        # Should have activate permission
        assert self.batch_viewset.check_batch_permission(self.batch, limited_manager, 'can_activate') is True
        
        # Should not have verify permission
        assert self.batch_viewset.check_batch_permission(self.batch, limited_manager, 'can_verify') is False
        
        # Should not have void permission
        assert self.batch_viewset.check_batch_permission(self.batch, limited_manager, 'void_batches') is False
        
        # Should still have basic access
        assert self.batch_viewset.check_batch_permission(self.batch, limited_manager) is True
    
    def test_batch_manager_permissions(self):
        """Test batch-specific manager permissions"""
        # Create a user who is only a batch manager (not event manager)
        batch_only_user = UserFactory()
        
        # Create event membership without specific permissions
        event_membership = EventMembershipFactory(
            event=self.event,
            user=batch_only_user,
            permissions={},  # No event-level permissions
            invited_by=self.owner
        )
        
        # Create batch membership with specific permissions
        BatchMembershipFactory(
            batch=self.batch,
            membership=event_membership,
            can_activate=True,
            can_verify=False,
            assigned_by=self.owner
        )
        
        # Should have activate permission at batch level
        assert self.batch_viewset.check_batch_permission(self.batch, batch_only_user, 'can_activate') is True
        
        # Should not have verify permission at batch level
        assert self.batch_viewset.check_batch_permission(self.batch, batch_only_user, 'can_verify') is False
        
        # Should have basic access
        assert self.batch_viewset.check_batch_permission(self.batch, batch_only_user) is True
    
    def test_outsider_no_permissions(self):
        """Test that outsiders have no permissions"""
        assert self.batch_viewset.check_batch_permission(self.batch, self.outsider) is False
        assert self.batch_viewset.check_batch_permission(self.batch, self.outsider, 'can_activate') is False
        assert self.batch_viewset.check_batch_permission(self.batch, self.outsider, 'can_verify') is False
        assert self.batch_viewset.check_batch_permission(self.batch, self.outsider, 'void_batches') is False
    
    def test_permission_key_mapping(self):
        """Test that permission keys are properly mapped"""
        # Test that legacy keys are mapped to new keys
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'can_verify') is True
        
        # Test that new keys work directly
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'void_batches') is True
        assert self.batch_viewset.check_batch_permission(self.batch, self.manager, 'create_batches') is True
    
    def test_inactive_memberships_ignored(self):
        """Test that inactive memberships are ignored"""
        # Create inactive event membership
        inactive_user = UserFactory()
        EventMembershipFactory(
            event=self.event,
            user=inactive_user,
            permissions={
                'activate_tickets': True,
                'verify_tickets': True
            },
            invited_by=self.owner,
            is_active=False  # Inactive membership
        )
        
        # Should not have any permissions
        assert self.batch_viewset.check_batch_permission(self.batch, inactive_user) is False
        assert self.batch_viewset.check_batch_permission(self.batch, inactive_user, 'can_activate') is False
    
    def test_batch_membership_inactive_ignored(self):
        """Test that inactive batch memberships are ignored"""
        # Create user with active event membership but inactive batch membership
        batch_user = UserFactory()
        event_membership = EventMembershipFactory(
            event=self.event,
            user=batch_user,
            permissions={},  # No event-level permissions
            invited_by=self.owner
        )
        
        BatchMembershipFactory(
            batch=self.batch,
            membership=event_membership,
            can_activate=True,
            can_verify=True,
            is_active=False,  # Inactive batch membership
            assigned_by=self.owner
        )
        
        # Should have basic access through event membership
        assert self.batch_viewset.check_batch_permission(self.batch, batch_user) is True
        
        # Should not have batch-specific permissions due to inactive batch membership
        assert self.batch_viewset.check_batch_permission(self.batch, batch_user, 'can_activate') is False
        assert self.batch_viewset.check_batch_permission(self.batch, batch_user, 'can_verify') is False


@pytest.mark.django_db(transaction=True)
class TestPermissionKeyMapping:
    """Test permission key mapping and backward compatibility"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.event = EventFactory(created_by=self.owner)
        self.ticket_type = TicketTypeFactory(event=self.event, created_by=self.owner)
        self.batch = BatchFactory(
            event=self.event,
            ticket_type=self.ticket_type,
            created_by=self.owner
        )
        self.batch_viewset = BatchViewSet()
    
    def test_legacy_permission_keys_mapped(self):
        """Test that legacy permission keys are properly mapped"""
        user = UserFactory()
        EventMembershipFactory(
            event=self.event,
            user=user,
            permissions={
                'activate_tickets': True,
                'verify_tickets': False,
                'void_batches': True,
                'create_batches': False
            },
            invited_by=self.owner
        )
        
        # Test legacy key mapping
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'can_verify') is False
        
        # Test direct key usage
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'void_batches') is True
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'create_batches') is False
    
    def test_unknown_permission_key_fallback(self):
        """Test that unknown permission keys fall back to the key itself"""
        user = UserFactory()
        EventMembershipFactory(
            event=self.event,
            user=user,
            permissions={
                'custom_permission': True,
                'another_custom': False
            },
            invited_by=self.owner
        )
        
        # Unknown keys should be looked up directly in permissions dict
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'custom_permission') is True
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'another_custom') is False
        assert self.batch_viewset.check_batch_permission(self.batch, user, 'nonexistent') is False


@pytest.mark.django_db(transaction=True)
class TestComplexPermissionScenarios:
    """Test complex permission scenarios with multiple membership levels"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.event = EventFactory(created_by=self.owner)
        self.ticket_type = TicketTypeFactory(event=self.event, created_by=self.owner)
        
        # Create multiple batches
        self.batch1 = BatchFactory(
            event=self.event,
            ticket_type=self.ticket_type,
            created_by=self.owner
        )
        self.batch2 = BatchFactory(
            event=self.event,
            ticket_type=self.ticket_type,
            created_by=self.owner
        )
        
        self.batch_viewset = BatchViewSet()
    
    def test_event_permission_overrides_batch_permission(self):
        """Test that event-level permissions take precedence over batch-level restrictions"""
        user = UserFactory()
        
        # Create event membership with verify permission
        event_membership = EventMembershipFactory(
            event=self.event,
            user=user,
            permissions={
                'verify_tickets': True
            },
            invited_by=self.owner
        )
        
        # Create batch membership that restricts verify permission
        BatchMembershipFactory(
            batch=self.batch1,
            membership=event_membership,
            can_activate=True,
            can_verify=False,  # Restricted at batch level
            assigned_by=self.owner
        )
        
        # Event-level permission should override batch-level restriction
        assert self.batch_viewset.check_batch_permission(self.batch1, user, 'can_verify') is True
    
    def test_batch_specific_permissions(self):
        """Test that batch-specific permissions work correctly"""
        user = UserFactory()
        
        # Create event membership without specific permissions
        event_membership = EventMembershipFactory(
            event=self.event,
            user=user,
            permissions={},  # No event-level permissions
            invited_by=self.owner
        )
        
        # Create batch membership for batch1 with activate permission
        BatchMembershipFactory(
            batch=self.batch1,
            membership=event_membership,
            can_activate=True,
            can_verify=False,
            assigned_by=self.owner
        )
        
        # Create batch membership for batch2 with verify permission
        BatchMembershipFactory(
            batch=self.batch2,
            membership=event_membership,
            can_activate=False,
            can_verify=True,
            assigned_by=self.owner
        )
        
        # Should have different permissions for different batches
        assert self.batch_viewset.check_batch_permission(self.batch1, user, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch1, user, 'can_verify') is False
        
        assert self.batch_viewset.check_batch_permission(self.batch2, user, 'can_activate') is False
        assert self.batch_viewset.check_batch_permission(self.batch2, user, 'can_verify') is True
    
    def test_multiple_membership_paths(self):
        """Test user with multiple paths to permissions"""
        user = UserFactory()
        
        # Create event membership with limited permissions
        event_membership = EventMembershipFactory(
            event=self.event,
            user=user,
            permissions={
                'activate_tickets': True
            },
            invited_by=self.owner
        )
        
        # Create batch membership with additional permissions
        BatchMembershipFactory(
            batch=self.batch1,
            membership=event_membership,
            can_activate=True,  # Redundant with event permission
            can_verify=True,    # Additional permission at batch level
            assigned_by=self.owner
        )
        
        # Should have permissions from both levels
        assert self.batch_viewset.check_batch_permission(self.batch1, user, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch1, user, 'can_verify') is True
        
        # For batch2 (no batch membership), should only have event-level permissions
        assert self.batch_viewset.check_batch_permission(self.batch2, user, 'can_activate') is True
        assert self.batch_viewset.check_batch_permission(self.batch2, user, 'can_verify') is False
