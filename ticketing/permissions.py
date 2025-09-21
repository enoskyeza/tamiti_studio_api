from django.contrib.auth import get_user_model
from .models import EventMembership, BatchMembership

User = get_user_model()


class TicketingPermissionService:
    """Service to handle ticketing-specific permissions"""
    
    @staticmethod
    def get_user_managed_events(user):
        """Get all events that a user can manage"""
        if user.is_superuser:
            from .models import Event
            return Event.objects.all()
        
        return EventMembership.objects.filter(
            user=user, 
            is_active=True
        ).select_related('event').values_list('event', flat=True)
    
    @staticmethod
    def can_manage_event(user, event):
        """Check if user can manage a specific event"""
        if user.is_superuser:
            return True
        
        return EventMembership.objects.filter(
            user=user,
            event=event,
            is_active=True
        ).exists()
    
    @staticmethod
    def can_perform_action(user, event, action):
        """Check if user can perform specific action on event"""
        if user.is_superuser:
            return True
        
        try:
            membership = EventMembership.objects.get(
                user=user,
                event=event,
                is_active=True
            )
            return membership.has_permission(action)
        except EventMembership.DoesNotExist:
            return False
    
    @staticmethod
    def can_manage_batch(user, batch, action='activate_tickets'):
        """Check if user can manage a specific batch"""
        if user.is_superuser:
            return True
        
        # Check if user is event member
        event_membership = EventMembership.objects.filter(
            user=user,
            event=batch.event,
            is_active=True
        ).first()
        
        if not event_membership:
            return False
        
        # Event owners can do everything
        if event_membership.role == 'owner':
            return True
        
        # Check event-level permissions
        if event_membership.has_permission(action):
            # Check if there are batch-specific restrictions
            batch_assignment = BatchMembership.objects.filter(
                batch=batch,
                membership=event_membership
            ).first()
            
            if batch_assignment:
                # Batch-specific permissions override event permissions
                if action == 'activate_tickets':
                    return batch_assignment.can_activate
                elif action == 'verify_tickets':
                    return batch_assignment.can_verify
            
            return True
        
        return False
    
    @staticmethod
    def get_user_batches(user):
        """Get all batches that a user can access"""
        if user.is_superuser:
            from .models import Batch
            return Batch.objects.all()
        
        # Get events user manages
        managed_events = TicketingPermissionService.get_user_managed_events(user)
        
        from .models import Batch
        return Batch.objects.filter(event__in=managed_events)
    
    @staticmethod
    def create_event_owner(event, user, assigned_by):
        """Create an event owner with full permissions"""
        membership, created = EventMembership.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                'role': 'owner',
                'permissions': {
                    'activate_tickets': True,
                    'verify_tickets': True, 
                    'create_batches': True,
                    'void_batches': True,
                    'export_batches': True,
                    'manage_staff': True,
                    'view_reports': True
                },
                'invited_by': assigned_by
            }
        )
        return membership
    
    @staticmethod
    def create_event_manager(event, user, permissions, assigned_by):
        """Create an event manager with specific permissions"""
        # Convert list permissions to dict format if needed
        if isinstance(permissions, list):
            permission_dict = {}
            for perm in permissions:
                permission_dict[perm] = True
            permissions = permission_dict
        
        membership, created = EventMembership.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                'role': 'manager',
                'permissions': permissions,
                'invited_by': assigned_by
            }
        )
        if not created:
            # Update permissions if membership already exists
            membership.permissions = permissions
            membership.save()
        return membership
    
    @staticmethod
    def assign_membership_to_batch(batch, membership, can_activate=True, can_verify=True, assigned_by=None):
        """Assign a membership to a specific batch"""
        assignment, created = BatchMembership.objects.get_or_create(
            batch=batch,
            membership=membership,
            defaults={
                'can_activate': can_activate,
                'can_verify': can_verify,
                'assigned_by': assigned_by or membership.invited_by
            }
        )
        if not created:
            assignment.can_activate = can_activate
            assignment.can_verify = can_verify
            assignment.save()
        return assignment
