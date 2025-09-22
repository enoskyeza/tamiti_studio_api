from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from ticketing.models import (
    Event, EventMembership, BatchMembership, 
    Batch, TemporaryUser
)

class Command(BaseCommand):
    help = 'Migrate data from legacy EventManager/BatchManager to new membership system'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Start a transaction
        with transaction.atomic():
            # Step 1: Migrate Temporary Users to Regular Users with is_temporary=True
            self.stdout.write("Migrating temporary users to regular users...")
            temp_user_mapping = self.migrate_temporary_users(User)
            
            # Step 2: Migrate Event Managers to Event Memberships
            self.stdout.write("Migrating event managers to event memberships...")
            self.migrate_event_managers(User, temp_user_mapping)
            
            # Step 3: Migrate Batch Managers to Batch Memberships
            self.stdout.write("Migrating batch managers to batch memberships...")
            self.migrate_batch_managers(User, temp_user_mapping)
            
            self.stdout.write(self.style.SUCCESS('Successfully migrated all data!'))
    
    def migrate_temporary_users(self, User):
        """Migrate TemporaryUser to regular User with is_temporary=True"""
        temp_user_mapping = {}
        
        for temp_user in TemporaryUser.objects.all():
            # Check if user already exists
            user = User.objects.filter(
                username=temp_user.username,
                is_temporary=True,
                created_for_event=temp_user.event
            ).first()
            
            if not user:
                # Create new temporary user
                user = User.objects.create_user(
                    username=temp_user.username,
                    password=temp_user.password_hash,
                    email=f"{temp_user.username}@temp.local",
                    is_temporary=True,
                    created_for_event=temp_user.event,
                    is_active=temp_user.is_active,
                    last_login=temp_user.last_login,
                    date_joined=temp_user.created_at or timezone.now(),
                )
                self.stdout.write(f"Created temporary user: {user.username}")
            
            # Store permissions mapping
            temp_user_mapping[temp_user.id] = {
                'user': user,
                'can_activate': temp_user.can_activate,
                'can_verify': temp_user.can_verify or temp_user.can_scan,
            }
        
        return temp_user_mapping
    
    def migrate_event_managers(self, User, temp_user_mapping):
        """Migrate EventManager to EventMembership"""
        from ticketing.models import EventManager
        
        for manager in EventManager.objects.all():
            user = None
            permissions = {}
            
            if manager.user_id:
                # Regular user
                user = manager.user
            elif manager.temp_user_id and manager.temp_user_id in temp_user_mapping:
                # Temporary user that was just migrated
                user = temp_user_mapping[manager.temp_user_id]['user']
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping EventManager {manager.id} - no valid user reference"
                    )
                )
                continue
            
            # Check if membership already exists
            if EventMembership.objects.filter(
                user=user, 
                event=manager.event
            ).exists():
                self.stdout.write(
                    f"Membership already exists for {user.username} in {manager.event.name}"
                )
                continue
            
            # Map old role to new role
            role_mapping = {
                'admin': 'manager',  # Map old 'admin' to 'manager'
                'manager': 'manager',
                'staff': 'staff',
                'owner': 'owner',
            }
            role = role_mapping.get(manager.role, 'staff')
            
            # Create permissions dict
            permissions = {}
            
            # Add permissions from temp user if applicable
            if manager.temp_user_id and manager.temp_user_id in temp_user_mapping:
                temp_data = temp_user_mapping[manager.temp_user_id]
                if temp_data['can_activate']:
                    permissions['activate_tickets'] = True
                if temp_data['can_verify']:
                    permissions['verify_tickets'] = True
            
            # Add permissions from manager's permissions list
            if hasattr(manager, 'permissions') and isinstance(manager.permissions, list):
                for perm in manager.permissions:
                    permissions[perm] = True
            
            # Create the membership
            membership = EventMembership.objects.create(
                user=user,
                event=manager.event,
                role=role,
                permissions=permissions,
                invited_by=manager.assigned_by,
                invited_at=manager.created_at or timezone.now(),
                is_active=getattr(manager, 'is_active', True),
            )
            
            self.stdout.write(
                f"Created membership: {user.username} as {role} in {manager.event.name}"
            )
    
    def migrate_batch_managers(self, User, temp_user_mapping):
        """Migrate BatchManager to BatchMembership"""
        from ticketing.models import BatchManager
        
        for batch_manager in BatchManager.objects.all():
            try:
                # Get the user from the EventManager
                event_manager = batch_manager.manager
                user = None
                
                if event_manager.user_id:
                    user = event_manager.user
                elif event_manager.temp_user_id and event_manager.temp_user_id in temp_user_mapping:
                    user = temp_user_mapping[event_manager.temp_user_id]['user']
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping BatchManager {batch_manager.id} - no valid user reference"
                        )
                    )
                    continue
                
                # Find the corresponding EventMembership
                try:
                    membership = EventMembership.objects.get(
                        user=user,
                        event=batch_manager.batch.event
                    )
                except EventMembership.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No membership found for {user.username} in {batch_manager.batch.event.name}"
                        )
                    )
                    continue
                
                # Create BatchMembership if it doesn't exist
                if not BatchMembership.objects.filter(
                    batch=batch_manager.batch,
                    membership=membership
                ).exists():
                    BatchMembership.objects.create(
                        batch=batch_manager.batch,
                        membership=membership,
                        can_activate=getattr(batch_manager, 'can_activate', True),
                        can_verify=getattr(batch_manager, 'can_verify', True),
                        assigned_by=(
                            batch_manager.assigned_by or 
                            getattr(event_manager, 'assigned_by', None) or
                            User.objects.filter(is_superuser=True).first()
                        ),
                        is_active=getattr(batch_manager, 'is_active', True),
                    )
                    self.stdout.write(
                        f"Created batch membership: {user.username} for batch {batch_manager.batch.batch_number}"
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error migrating BatchManager {getattr(batch_manager, 'id', 'unknown')}: {str(e)}"
                    )
                )
