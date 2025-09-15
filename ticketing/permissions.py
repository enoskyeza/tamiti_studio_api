from django.contrib.auth import get_user_model
from .models import EventManager, BatchManager

User = get_user_model()


class TicketingPermissionService:
    """Service to handle ticketing-specific permissions"""
    
    @staticmethod
    def get_user_managed_events(user):
        """Get all events that a user can manage"""
        if user.is_superuser:
            from .models import Event
            return Event.objects.all()
        
        return EventManager.objects.filter(
            user=user, 
            is_active=True
        ).select_related('event').values_list('event', flat=True)
    
    @staticmethod
    def can_manage_event(user, event):
        """Check if user can manage a specific event"""
        if user.is_superuser:
            return True
        
        return EventManager.objects.filter(
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
            manager = EventManager.objects.get(
                user=user,
                event=event,
                is_active=True
            )
            return manager.has_permission(action)
        except EventManager.DoesNotExist:
            return False
    
    @staticmethod
    def can_manage_batch(user, batch, action='activate_tickets'):
        """Check if user can manage a specific batch"""
        if user.is_superuser:
            return True
        
        # Check if user is event manager
        event_manager = EventManager.objects.filter(
            user=user,
            event=batch.event,
            is_active=True
        ).first()
        
        if not event_manager:
            return False
        
        # Event owners can do everything
        if event_manager.role == 'owner':
            return True
        
        # Check event-level permissions
        if event_manager.has_permission(action):
            # Check if there are batch-specific restrictions
            batch_assignment = BatchManager.objects.filter(
                batch=batch,
                manager=event_manager
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
        manager, created = EventManager.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                'role': 'owner',
                'permissions': [
                    'activate_tickets',
                    'verify_tickets', 
                    'create_batches',
                    'void_batches',
                    'export_batches',
                    'manage_staff',
                    'view_reports'
                ],
                'assigned_by': assigned_by
            }
        )
        return manager
    
    @staticmethod
    def create_event_manager(event, user, permissions, assigned_by):
        """Create an event manager with specific permissions"""
        manager, created = EventManager.objects.get_or_create(
            event=event,
            user=user,
            defaults={
                'role': 'manager',
                'permissions': permissions,
                'assigned_by': assigned_by
            }
        )
        if not created:
            # Update permissions if manager already exists
            manager.permissions = permissions
            manager.save()
        return manager
    
    @staticmethod
    def assign_manager_to_batch(batch, manager, can_activate=True, can_verify=True, assigned_by=None):
        """Assign a manager to a specific batch"""
        assignment, created = BatchManager.objects.get_or_create(
            batch=batch,
            manager=manager,
            defaults={
                'can_activate': can_activate,
                'can_verify': can_verify,
                'assigned_by': assigned_by or manager.assigned_by
            }
        )
        if not created:
            assignment.can_activate = can_activate
            assignment.can_verify = can_verify
            assignment.save()
        return assignment
