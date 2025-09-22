# tests/test_temporary_users.py
"""
Test temporary user management and permissions
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from tests.factories import UserFactory, EventFactory
from users.models import User


@pytest.mark.django_db(transaction=True)
class TestTemporaryUserManagement:
    """Test temporary user creation, management, and permissions"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.other_owner = UserFactory()
        self.outsider = UserFactory()
        self.staff = UserFactory(is_staff=True)
        
        self.event = EventFactory(created_by=self.owner)
        self.other_event = EventFactory(created_by=self.other_owner)
        
        self.owner_client = APIClient()
        self.other_owner_client = APIClient()
        self.outsider_client = APIClient()
        self.staff_client = APIClient()
        
        self.owner_client.force_authenticate(user=self.owner)
        self.other_owner_client.force_authenticate(user=self.other_owner)
        self.outsider_client.force_authenticate(user=self.outsider)
        self.staff_client.force_authenticate(user=self.staff)
    
    def test_event_owner_can_create_temporary_user(self):
        """Test that event owners can Create temporary Users for their events"""
        url = reverse('temporaryuser-list')
        data = {
            'event': self.event.id,
            'username': 'temp_scanner_001',
            'role': 'scanner',
            'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
        }
        
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify the temporary user was created correctly
        temp_user = User.objects.get(username='temp_scanner_001')
        assert temp_user.is_temporary is True
        assert temp_user.created_for_event == self.event
        assert temp_user.role == 'scanner'
    
    def test_staff_can_create_temporary_user(self):
        """Test that staff can Create temporary Users for any event"""
        url = reverse('temporaryuser-list')
        data = {
            'event': self.event.id,
            'username': 'temp_staff_001',
            'role': 'activator',
            'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
        }
        
        response = self.staff_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_outsider_cannot_create_temporary_user(self):
        """Test that non-owners cannot Create temporary Users"""
        url = reverse('temporaryuser-list')
        data = {
            'event': self.event.id,
            'username': 'temp_unauthorized_001',
            'role': 'scanner',
            'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
        }
        
        response = self.outsider_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify no temporary user was created
        assert not User.objects.filter(username='temp_unauthorized_001').exists()
    
    def test_owner_cannot_create_temp_user_for_other_event(self):
        """Test that event owners cannot Create temporary Users for other events"""
        url = reverse('temporaryuser-list')
        data = {
            'event': self.other_event.id,  # Different owner's event
            'username': 'temp_cross_event_001',
            'role': 'scanner',
            'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
        }
        
        response = self.owner_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify no temporary user was created
        assert not User.objects.filter(username='temp_cross_event_001').exists()
    
    def test_temporary_user_tied_to_one_event(self):
        """Test that temporary users are tied to the specific event they were created for"""
        # Create temporary User for first event
        temp_user = User.objects.create_user(
            username='temp_event_specific',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Verify the user is tied to the correct event
        assert temp_user.created_for_event == self.event
        assert temp_user.created_for_event != self.other_event
        
        # Test that the user appears in the correct event's temporary user list
        url = reverse('temporaryuser-list')
        response = self.owner_client.get(url, {'event': self.event.id})
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'temp_event_specific' in usernames
        
        # Test that the user doesn't appear in other event's list
        response = self.other_owner_client.get(url, {'event': self.other_event.id})
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'temp_event_specific' not in usernames
    
    def test_temporary_user_expiry(self):
        """Test temporary user expiry functionality"""
        # Create expired temporary user
        expired_user = User.objects.create_user(
            username='temp_expired',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() - timedelta(days=1)  # Expired
        )
        
        # Create active temporary user
        active_user = User.objects.create_user(
            username='temp_active',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7)  # Active
        )
        
        # Test expiry check
        assert expired_user.is_expired() is True
        assert active_user.is_expired() is False
    
    def test_temporary_user_deactivation_permissions(self):
        """Test that only event owners can deactivate temporary users"""
        # Create temporary User
        temp_user = User.objects.create_user(
            username='temp_deactivate_test',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True
        )
        
        url = reverse('temporaryuser-deactivate', kwargs={'pk': temp_user.pk})
        
        # Owner should be able to deactivate
        response = self.owner_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        temp_user.refresh_from_db()
        assert temp_user.is_active is False
        
        # Reset for next test
        temp_user.is_active = True
        temp_user.save()
        
        # Staff should be able to deactivate
        response = self.staff_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Reset for next test
        temp_user.is_active = True
        temp_user.save()
        
        # Outsider should not be able to deactivate
        response = self.outsider_client.post(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND  # Due to queryset filtering
    
    def test_temporary_user_activation_permissions(self):
        """Test that only event owners can activate temporary users"""
        # Create inactive temporary user
        temp_user = User.objects.create_user(
            username='temp_activate_test',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7),
            is_active=False
        )
        
        url = reverse('temporaryuser-activate', kwargs={'pk': temp_user.pk})
        
        # Owner should be able to activate
        response = self.owner_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        temp_user.refresh_from_db()
        assert temp_user.is_active is True
    
    def test_cannot_activate_expired_temporary_user(self):
        """Test that expired temporary users cannot be activated"""
        # Create expired temporary user
        expired_user = User.objects.create_user(
            username='temp_expired_activate',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
            is_active=False
        )
        
        url = reverse('temporaryuser-activate', kwargs={'pk': expired_user.pk})
        
        response = self.owner_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'expired' in response.data['error'].lower()
        
        expired_user.refresh_from_db()
        assert expired_user.is_active is False
    
    def test_temporary_user_queryset_filtering(self):
        """Test that temporary user querysets are properly filtered by permissions"""
        # Create temporary Users for different events
        temp_user1 = User.objects.create_user(
            username='temp_event1',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        temp_user2 = User.objects.create_user(
            username='temp_event2',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.other_event,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        url = reverse('temporaryuser-list')
        
        # Owner should only see their event's temporary users
        response = self.owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'temp_event1' in usernames
        assert 'temp_event2' not in usernames
        
        # Other owner should only see their event's temporary users
        response = self.other_owner_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'temp_event1' not in usernames
        assert 'temp_event2' in usernames
        
        # Staff should see all temporary users
        response = self.staff_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'temp_event1' in usernames
        assert 'temp_event2' in usernames
    
    def test_temporary_user_search_functionality(self):
        """Test search functionality for temporary users"""
        # Create temporary Users with different names
        User.objects.create_user(
            username='scanner_gate_a',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        User.objects.create_user(
            username='activator_main',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        url = reverse('temporaryuser-list')
        
        # Search for scanner
        response = self.owner_client.get(url, {'search': 'scanner'})
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'scanner_gate_a' in usernames
        assert 'activator_main' not in usernames
        
        # Search for activator
        response = self.owner_client.get(url, {'search': 'activator'})
        assert response.status_code == status.HTTP_200_OK
        
        usernames = [user['username'] for user in response.data['results']]
        assert 'scanner_gate_a' not in usernames
        assert 'activator_main' in usernames


@pytest.mark.django_db(transaction=True)
class TestTemporaryUserTicketOperations:
    """Test that temporary users cannot activate/verify tickets outside their assignment"""
    
    def setup_method(self):
        """Set up test data"""
        self.owner = UserFactory()
        self.other_owner = UserFactory()
        
        self.event = EventFactory(created_by=self.owner)
        self.other_event = EventFactory(created_by=self.other_owner)
        
        # Create temporary User for first event
        self.temp_user = User.objects.create_user(
            username='temp_scanner',
            password='temp_pass',
            is_temporary=True,
            created_for_event=self.event,
            expires_at=timezone.now() + timedelta(days=7),
            role='scanner'
        )
        
        self.temp_client = APIClient()
        self.temp_client.force_authenticate(user=self.temp_user)
    
    def test_temporary_user_cannot_access_other_event_tickets(self):
        """Test that temporary users cannot access tickets from other events"""
        from tests.factories import BatchFactory, TicketFactory, TicketTypeFactory
        
        # Create ticket for other event
        other_ticket_type = TicketTypeFactory(event=self.other_event, created_by=self.other_owner)
        other_batch = BatchFactory(
            event=self.other_event,
            ticket_type=other_ticket_type,
            created_by=self.other_owner
        )
        other_ticket = TicketFactory(batch=other_batch, ticket_type=other_ticket_type)
        
        # Try to activate ticket from other event
        url = reverse('ticket-activate')
        data = {
            'qr_code': other_ticket.qr_code,
            'buyer_info': {'name': 'Test Buyer'}
        }
        
        response = self.temp_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_temporary_user_role_based_permissions(self):
        """Test that temporary user permissions are based on their role"""
        # This would be expanded based on how roles are implemented
        # For now, we test that the temporary user exists and has the correct role
        assert self.temp_user.role == 'scanner'
        assert self.temp_user.is_temporary is True
        assert self.temp_user.created_for_event == self.event
