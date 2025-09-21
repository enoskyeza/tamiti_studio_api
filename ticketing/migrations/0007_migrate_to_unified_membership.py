from django.db import migrations


def migrate_temporary_users_to_regular_users(apps, schema_editor):
    """Convert TemporaryUser records to User records with is_temporary=True"""
    User = apps.get_model('users', 'User')
    TemporaryUser = apps.get_model('ticketing', 'TemporaryUser')
    
    created_users = []
    
    for temp_user in TemporaryUser.objects.all():
        # Create permissions dict from TemporaryUser capabilities
        temp_permissions = {}
        if getattr(temp_user, 'can_activate', False):
            temp_permissions['activate_tickets'] = True
        if getattr(temp_user, 'can_verify', False):
            temp_permissions['verify_tickets'] = True
        if getattr(temp_user, 'can_scan', False) and 'verify_tickets' not in temp_permissions:
            temp_permissions['verify_tickets'] = True
        
        # Check if user already exists (from previous migration run)
        existing_user = User.objects.filter(
            username=temp_user.username,
            is_temporary=True,
            created_for_event_id=temp_user.event_id
        ).first()
        
        if existing_user:
            user = existing_user
            print(f"Found existing migrated user: {temp_user.username} -> User {user.id}")
        else:
            # Create a new User record with temporary flag
            user = User.objects.create(
                username=temp_user.username,
                password=temp_user.password_hash,  # Copy password hash directly
                is_temporary=True,
                expires_at=temp_user.expires_at,
                created_for_event_id=temp_user.event_id,  # Use ID instead of object
                auto_generated_username=True,
                email=f"{temp_user.username}@temp.local",
                is_active=temp_user.is_active,
                last_login=temp_user.last_login,
                date_joined=temp_user.created_at,
            )
            print(f"Migrated TemporaryUser {temp_user.username} to User {user.id}")
        
        # Store the temp permissions for later use in EventMembership creation
        created_users.append((temp_user.id, user.id, 'staff', temp_permissions))
    
    return created_users


def migrate_event_managers_to_memberships(apps, schema_editor):
    """Convert EventManager records to EventMembership records"""
    User = apps.get_model('users', 'User')
    EventManager = apps.get_model('ticketing', 'EventManager')
    EventMembership = apps.get_model('ticketing', 'EventMembership')
    TemporaryUser = apps.get_model('ticketing', 'TemporaryUser')
    
    # First, get mapping of temp users to regular users with their permissions
    temp_user_mapping = {}
    for temp_user in TemporaryUser.objects.all():
        try:
            regular_user = User.objects.get(
                username=temp_user.username,
                is_temporary=True,
                created_for_event_id=temp_user.event_id
            )
            # Create permissions dict from TemporaryUser capabilities
            temp_permissions = {}
            if getattr(temp_user, 'can_activate', False):
                temp_permissions['activate_tickets'] = True
            if getattr(temp_user, 'can_verify', False):
                temp_permissions['verify_tickets'] = True
            if getattr(temp_user, 'can_scan', False) and 'verify_tickets' not in temp_permissions:
                temp_permissions['verify_tickets'] = True
            
            temp_user_mapping[temp_user.id] = {
                'user_id': regular_user.id,
                'role': 'staff',
                'permissions': temp_permissions
            }
        except User.DoesNotExist:
            print(f"Warning: Could not find migrated user for TemporaryUser {temp_user.username}")
    
    for event_manager in EventManager.objects.all():
        user_id = None
        
        if event_manager.user_id:
            # Regular user
            user_id = event_manager.user_id
        elif event_manager.temp_user_id:
            # Temporary user - get the migrated regular user
            temp_user_data = temp_user_mapping.get(event_manager.temp_user_id)
            if not temp_user_data:
                print(f"Warning: Could not find migrated user for EventManager {event_manager.id}")
                continue
            user_id = temp_user_data['user_id']
        else:
            print(f"Warning: EventManager {event_manager.id} has no user reference")
            continue
        
        # Convert permissions list to dict, merging with temp user permissions if applicable
        permissions_dict = {}
        if event_manager.permissions:
            for perm in event_manager.permissions:
                permissions_dict[perm] = True
        
        # If this is a temporary user, merge their capabilities
        if event_manager.temp_user_id:
            temp_user_data = temp_user_mapping.get(event_manager.temp_user_id)
            if temp_user_data and temp_user_data['permissions']:
                permissions_dict.update(temp_user_data['permissions'])
        
        # Use role from event manager (choices already validated)
        role = event_manager.role
        
        # Create EventMembership
        membership = EventMembership.objects.create(
            user_id=user_id,
            event_id=event_manager.event_id,
            role=role,
            permissions=permissions_dict,
            invited_by_id=event_manager.assigned_by_id,
            invited_at=event_manager.created_at,
            is_active=event_manager.is_active,
        )
        
        print(f"Migrated EventManager {event_manager.id} to EventMembership {membership.id}")


def migrate_batch_managers_to_batch_memberships(apps, schema_editor):
    """Convert BatchManager records to BatchMembership records"""
    User = apps.get_model('users', 'User')
    BatchManager = apps.get_model('ticketing', 'BatchManager')
    BatchMembership = apps.get_model('ticketing', 'BatchMembership')
    EventMembership = apps.get_model('ticketing', 'EventMembership')
    TemporaryUser = apps.get_model('ticketing', 'TemporaryUser')
    
    for batch_manager in BatchManager.objects.all():
        # Find the corresponding EventMembership
        try:
            # Get the user from the EventManager
            event_manager = batch_manager.manager
            user_id = None
            
            if event_manager.user_id:
                user_id = event_manager.user_id
            elif event_manager.temp_user_id:
                # Find the migrated user
                temp_user = event_manager.temp_user
                try:
                    migrated_user = User.objects.get(
                        username=temp_user.username,
                        is_temporary=True,
                        created_for_event_id=temp_user.event_id
                    )
                    user_id = migrated_user.id
                except User.DoesNotExist:
                    print(f"Warning: Could not find migrated user for BatchManager {batch_manager.id}")
                    continue
            
            if not user_id:
                continue
                
            membership = EventMembership.objects.get(
                user_id=user_id,
                event_id=batch_manager.batch.event_id
            )
            
            BatchMembership.objects.create(
                batch_id=batch_manager.batch_id,
                membership_id=membership.id,
                can_activate=batch_manager.can_activate,
                can_verify=batch_manager.can_verify,
                assigned_by_id=batch_manager.assigned_by_id if batch_manager.assigned_by_id else event_manager.assigned_by_id,
                is_active=True,
            )
            
            print(f"Migrated BatchManager {batch_manager.id} to BatchMembership")
            
        except EventMembership.DoesNotExist:
            print(f"Warning: Could not find EventMembership for BatchManager {batch_manager.id}")
        except Exception as e:
            print(f"Error migrating BatchManager {batch_manager.id}: {e}")


def reverse_migration(apps, schema_editor):
    """Reverse the migration by deleting the new records"""
    User = apps.get_model('users', 'User')
    EventMembership = apps.get_model('ticketing', 'EventMembership')
    BatchMembership = apps.get_model('ticketing', 'BatchMembership')
    
    # Delete all batch memberships
    BatchMembership.objects.all().delete()
    
    # Delete all event memberships
    EventMembership.objects.all().delete()
    
    # Delete temporary users that were created
    User.objects.filter(is_temporary=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ticketing', '0006_add_event_membership_models'),
        ('users', '0006_add_temporary_user_fields'),
    ]

    operations = [
        migrations.RunPython(
            code=lambda apps, schema_editor: (
                migrate_temporary_users_to_regular_users(apps, schema_editor),
                migrate_event_managers_to_memberships(apps, schema_editor),
                migrate_batch_managers_to_batch_memberships(apps, schema_editor),
            ),
            reverse_code=reverse_migration,
        ),
    ]
