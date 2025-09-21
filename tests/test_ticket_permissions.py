# tests/test_ticket_permissions.py
"""
Test ticket access permissions and security fixes
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from tests.factories import (
    UserFactory, EventFactory, EventMembershipFactory, BatchFactory, 
    BatchMembershipFactory, TicketFactory, TicketTypeFactory
)


@pytest.mark.django_db(transaction=True)
class TestTicketPermissions:
    """Test ticket access permissions and security"""
    
    def setup_method(self):
        """Set up test data"""
        # Create users
        self.owner = UserFactory()
        self.manager = UserFactory()
        self.batch_manager = UserFactory()
        self.outsider = UserFactory()
        self.staff = UserFactory(is_staff=True)
        
        # Create event owned by owner
        self.event = EventFactory(created_by=self.owner)
        
        # Create another event owned by outsider
        self.other_event = EventFactory(created_by=self.outsider)
        
        # Create ticket type
        self.ticket_type = TicketTypeFactory(event=self.event)
        
        # Create batch
        self.batch = BatchFactory(
            event=self.event, 
            created_by=self.owner
        )
        
        # Create batch for other event
        self.other_batch = BatchFactory(
            event=self.other_event,
            created_by=self.outsider
        )
        
        # Create tickets
        self.ticket1 = TicketFactory(batch=self.batch, ticket_type=self.ticket_type)
        self.ticket2 = TicketFactory(batch=self.batch, ticket_type=self.ticket_type)
        self.other_ticket = TicketFactory(batch=self.other_batch)
        
        # Create event membership for manager
        self.event_membership = EventMembershipFactory(
            event=self.event,
            user=self.manager,
            role='manager',
            permissions={
                'activate_tickets': True,
                'verify_tickets': True
            },
            invited_by=self.owner
        )
        
        # Create batch membership for batch_manager
        self.batch_membership = BatchMembershipFactory(
            batch=self.batch,
            membership=self.event_membership,
            can_activate=True,
            can_verify=True,
            assigned_by=self.owner
        )
        
        # Create API clients
        self.owner_client = APIClient()
        self.manager_client = APIClient()
        self.batch_manager_client = APIClient()
        self.outsider_client = APIClient()
        self.staff_client = APIClient()
        
        # Authenticate clients
        self.owner_client.force_authenticate(user=self.owner)
        self.manager_client.force_authenticate(user=self.manager)
        self.batch_manager_client.force_authenticate(user=self.batch_manager)
        self.outsider_client.force_authenticate(user=self.outsider)
        self.staff_client.force_authenticate(user=self.staff)
    
    def test_ticket_list_owner_access(self):
        """Test that event owner can see their tickets"""
        url = reverse('ticket-list')
        response = self.owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Owner should see their tickets
        ticket_ids = [ticket['id'] for ticket in response.data['results']]
        assert self.ticket1.id in ticket_ids
        assert self.ticket2.id in ticket_ids
        assert self.other_ticket.id not in ticket_ids
    
    def test_ticket_list_manager_access(self):
        """Test that event manager can see tickets for managed events"""
        url = reverse('ticket-list')
        response = self.manager_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Manager should see tickets for their managed event
        ticket_ids = [ticket['id'] for ticket in response.data['results']]
        assert self.ticket1.id in ticket_ids
        assert self.ticket2.id in ticket_ids
        assert self.other_ticket.id not in ticket_ids
    
    def test_ticket_list_outsider_access(self):
        """Test that outsiders get empty list or 403"""
        url = reverse('ticket-list')
        response = self.outsider_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Outsider should only see tickets for their own events
        ticket_ids = [ticket['id'] for ticket in response.data['results']]
        assert self.ticket1.id not in ticket_ids
        assert self.ticket2.id not in ticket_ids
        assert self.other_ticket.id in ticket_ids  # Their own ticket
    
    def test_ticket_list_staff_access(self):
        """Test that staff can see all tickets"""
        url = reverse('ticket-list')
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Staff should see all tickets
        ticket_ids = [ticket['id'] for ticket in response.data['results']]
        assert self.ticket1.id in ticket_ids
        assert self.ticket2.id in ticket_ids
        assert self.other_ticket.id in ticket_ids
    
    def test_ticket_detail_access_control(self):
        """Test ticket detail access control"""
        url = reverse('ticket-detail', kwargs={'pk': self.ticket1.pk})
        
        # Owner should have access
        response = self.owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Manager should have access
        response = self.manager_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Outsider should not have access
        response = self.outsider_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Staff should have access
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db(transaction=True)
class TestMembershipPermissions:
    """Test membership creation permissions and privilege escalation prevention"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.manager = UserFactory()
        self.batch_manager = UserFactory()
        self.outsider = UserFactory()
        self.staff = UserFactory(is_staff=True)
        
        self.event = EventFactory(created_by=self.owner)
        self.other_event = EventFactory(created_by=self.outsider)
        
        self.owner_client = APIClient()
        self.outsider_client = APIClient()
        self.staff_client = APIClient()
        
        self.owner_client.force_authenticate(user=self.owner)
        self.outsider_client.force_authenticate(user=self.outsider)
        self.staff_client.force_authenticate(user=self.staff)
    
    def test_event_membership_creation_owner_only(self):
        """Test that only event owners can create event memberships"""
        url = reverse('event-memberships-list')
        
        # Owner should be able to create membership for manager
        data = {
            'event': self.event.id,
            'user_id': self.manager.id,
            'role': 'manager',
            'permissions': {
                'activate_tickets': True
            }
        }
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Outsider should not be able to create membership for batch_manager
        data = {
            'event': self.event.id,
            'user_id': self.batch_manager.id,
            'role': 'staff',
            'permissions': {
                'verify_tickets': True
            }
        }
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Staff should be able to create membership for outsider
        data = {
            'event': self.event.id,
            'user_id': self.outsider.id,
            'role': 'staff',
            'permissions': {
                'verify_tickets': True
            }
        }
        response = self.staff_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_batch_membership_creation_owner_only(self):
        """Test that only event owners can create batch memberships"""
        # Create batch and event membership first
        batch = BatchFactory(event=self.event, created_by=self.owner)
        membership = EventMembershipFactory(
            event=self.event,
            user=self.outsider,
            invited_by=self.owner
        )
        
        url = reverse('batch-memberships-list')
        data = {
            'batch': batch.id,
            'membership_id': membership.id,
            'can_activate': True,
            'can_verify': True
        }
        
        # Owner should be able to create batch membership
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Outsider should not be able to create batch membership
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Staff should be able to create batch membership
        response = self.staff_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_privilege_escalation_prevention(self):
        """Test that users cannot escalate privileges by creating memberships"""
        url = reverse('event-memberships-list')
        
        # Outsider tries to make themselves owner of someone else's event
        data = {
            'event': self.event.id,
            'user_id': self.outsider.id,
            'role': 'owner',
            'permissions': {
                'activate_tickets': True,
                'verify_tickets': True,
                'create_batches': True,
                'void_batches': True
            }
        }
        
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db(transaction=True)
class TestTemporaryUserPermissions:
    """Test temporary user creation permissions"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.outsider = UserFactory()
        self.staff = UserFactory(is_staff=True)
        
        self.event = EventFactory(created_by=self.owner)
        
        self.owner_client = APIClient()
        self.outsider_client = APIClient()
        self.staff_client = APIClient()
        
        self.owner_client.force_authenticate(user=self.owner)
        self.outsider_client.force_authenticate(user=self.outsider)
        self.staff_client.force_authenticate(user=self.staff)
    
    def test_temporary_user_creation_owner_only(self):
        """Test that only event owners can Create temporary Users"""
        url = reverse('create-temporary-users-list')
        data = {
            'created_for_event': self.event.id,
            'username': 'temp_user',
            'password': 'testpass123',
            'can_activate': True,
            'can_verify': True
        }
        
        # Owner should be able to Create temporary User
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Outsider should not be able to Create temporary User
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Staff should be able to Create temporary User
        response = self.staff_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db(transaction=True)
class TestActivationVerificationFlows:
    """Test ticket activation and verification with permission checks"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.manager = UserFactory()
        self.outsider = UserFactory()
        
        self.event = EventFactory(created_by=self.owner)
        self.ticket_type = TicketTypeFactory(event=self.event)
        self.batch = BatchFactory(
            event=self.event,
            created_by=self.owner
        )
        
        self.ticket = TicketFactory(
            batch=self.batch,
            ticket_type=self.ticket_type,
            status='unused'
        )
        
        # Create event membership with permissions
        self.membership = EventMembershipFactory(
            event=self.event,
            user=self.manager,
            permissions={
                'activate_tickets': True,
                'verify_tickets': True
            },
            invited_by=self.owner
        )
        
        self.owner_client = APIClient()
        self.manager_client = APIClient()
        self.outsider_client = APIClient()
        
        self.owner_client.force_authenticate(user=self.owner)
        self.manager_client.force_authenticate(user=self.manager)
        self.outsider_client.force_authenticate(user=self.outsider)
    
    def test_ticket_activation_success_paths(self):
        """Test successful ticket activation"""
        url = reverse('ticket-activate')
        data = {
            'qr_code': self.ticket.qr_code,
            'buyer_info': {
                'name': 'John Doe',
                'phone': '0700123456'
            }
        }
        
        # Owner should be able to activate
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        
        # Reset ticket status for next test
        self.ticket.status = 'unused'
        self.ticket.save()
        
        # Manager with permissions should be able to activate
        response = self.manager_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_ticket_activation_permission_denied(self):
        """Test ticket activation permission denied"""
        url = reverse('ticket-activate')
        data = {
            'qr_code': self.ticket.qr_code,
            'buyer_info': {
                'name': 'John Doe',
                'phone': '0700123456'
            }
        }
        
        # Outsider should not be able to activate
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Check that scan log was created with permission_denied result
        from ticketing.models import ScanLog
        scan_log = ScanLog.objects.filter(
            qr_code=self.ticket.qr_code,
            result='permission_denied'
        ).first()
        assert scan_log is not None
        assert scan_log.error_message == 'No permission to activate tickets for this batch'
    
    def test_ticket_verification_success_paths(self):
        """Test successful ticket verification"""
        # First activate the ticket
        self.ticket.status = 'activated'
        self.ticket.save()
        
        url = reverse('ticket-verify')
        data = {
            'qr_code': self.ticket.qr_code,
            'gate': 'Main Gate'
        }
        
        # Owner should be able to verify
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        
        # Reset ticket status for next test
        self.ticket.status = 'activated'
        self.ticket.save()
        
        # Manager with permissions should be able to verify
        response = self.manager_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
    
    def test_ticket_verification_permission_denied(self):
        """Test ticket verification permission denied"""
        # First activate the ticket
        self.ticket.status = 'activated'
        self.ticket.save()
        
        url = reverse('ticket-verify')
        data = {
            'qr_code': self.ticket.qr_code,
            'gate': 'Main Gate'
        }
        
        # Outsider should not be able to verify
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Check that scan log was created with permission_denied result
        from ticketing.models import ScanLog
        scan_log = ScanLog.objects.filter(
            qr_code=self.ticket.qr_code,
            result='permission_denied'
        ).first()
        assert scan_log is not None
        assert scan_log.error_message == 'No permission to verify tickets for this batch'
    
    def test_duplicate_scan_handling(self):
        """Test duplicate scan detection"""
        # First activate and scan the ticket
        self.ticket.status = 'scanned'
        self.ticket.save()
        
        url = reverse('ticket-verify')
        data = {
            'qr_code': self.ticket.qr_code,
            'gate': 'Main Gate'
        }
        
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is False
        assert 'Already scanned' in response.data['error']
    
    def test_invalid_code_handling(self):
        """Test invalid QR code handling"""
        url = reverse('ticket-activate')
        data = {
            'qr_code': 'invalid_code_123',
            'buyer_info': {
                'name': 'John Doe'
            }
        }
        
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['success'] is False
        assert 'not found' in response.data['error'].lower()


@pytest.mark.django_db(transaction=True)
class TestBatchPermissions:
    """Test batch management permissions"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.manager = UserFactory()
        self.outsider = UserFactory()
        
        self.event = EventFactory(created_by=self.owner)
        self.ticket_type = TicketTypeFactory(event=self.event)
        self.batch = BatchFactory(
            event=self.event,
            created_by=self.owner
        )
        
        # Create manager with void permissions
        self.membership = EventMembershipFactory(
            event=self.event,
            user=self.manager,
            permissions={
                'void_batches': True
            },
            invited_by=self.owner
        )
        
        self.owner_client = APIClient()
        self.manager_client = APIClient()
        self.outsider_client = APIClient()
        
        self.owner_client.force_authenticate(user=self.owner)
        self.manager_client.force_authenticate(user=self.manager)
        self.outsider_client.force_authenticate(user=self.outsider)
    
    def test_batch_void_permissions(self):
        """Test batch voiding permissions"""
        url = reverse('batch-void', kwargs={'pk': self.batch.pk})
        data = {'reason': 'Test void'}
        
        # Owner should be able to void
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Reset batch status
        self.batch.status = 'active'
        self.batch.save()
        
        # Manager with void_batches permission should be able to void
        response = self.manager_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # Reset batch status
        self.batch.status = 'active'
        self.batch.save()
        
        # Outsider should not be able to void
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db(transaction=True)
class TestEventCreationPermissions:
    """Test event creation permissions"""
    
    def setup_method(self):
        """Set up test data"""
        self.user = UserFactory()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_authenticated_user_can_create_event(self):
        """Test that any authenticated user can create an event"""
        url = reverse('event-list')
        data = {
            'name': 'Test Event',
            'description': 'Test Description',
            'venue': 'Test Venue',
            'date': '2024-12-01T10:00:00Z'
        }
        
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['created_by'] == self.user.id
