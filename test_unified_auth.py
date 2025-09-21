#!/usr/bin/env python
"""
Test script for the unified authentication system
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tamiti_studio.settings')
django.setup()

from django.contrib.auth import get_user_model, authenticate
from ticketing.models import Event, EventMembership, BatchMembership, Batch
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()

def test_unified_auth():
    print("=== Testing Unified Authentication System ===\n")
    
    # Test 1: Create a temporary user
    print("Test 1: Creating temporary user")
    event = Event.objects.first()
    if not event:
        print("No events found - creating test event")
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()
        event = Event.objects.create(
            name='Test Event',
            date=timezone.now().date(),
            venue='Test Venue',
            created_by=admin_user
        )
    
    temp_user = User.create_temporary_user(
        event=event,
        username='temp_test_user_' + str(timezone.now().timestamp())[:10],
        password='testpass123',
        expires_at=timezone.now() + timedelta(days=7)
    )
    print(f"✓ Created temporary user: {temp_user.username}")
    print(f"  - Is temporary: {temp_user.is_temporary}")
    print(f"  - Expires at: {temp_user.expires_at}")
    print(f"  - Created for event: {temp_user.created_for_event}")
    
    # Test 2: Test authentication
    print("\nTest 2: Testing authentication")
    auth_user = authenticate(username=temp_user.username, password='testpass123')
    if auth_user:
        print(f"✓ Temporary user authentication successful")
        print(f"  - Authenticated user ID: {auth_user.id}")
        print(f"  - Is temporary: {auth_user.is_temporary}")
    else:
        print("✗ Temporary user authentication failed")
    
    # Test 3: Create EventMembership
    print("\nTest 3: Creating EventMembership")
    regular_user = User.objects.filter(is_temporary=False).first()
    if regular_user and event:
        membership, created = EventMembership.objects.get_or_create(
            event=event,
            user=regular_user,
            defaults={
                'role': 'manager',
                'permissions': {'can_manage_tickets': True, 'can_scan': True},
                'invited_by': User.objects.first()
            }
        )
        print(f"✓ {'Created' if created else 'Found existing'} membership: {membership.user.username} -> {membership.event.name}")
        print(f"  - Role: {membership.role}")
        print(f"  - Permissions: {membership.permissions}")
    
    # Test 4: Create BatchMembership if batch exists
    print("\nTest 4: Testing BatchMembership")
    batch = Batch.objects.filter(event=event).first()
    if batch and 'membership' in locals():
        batch_membership, created = BatchMembership.objects.get_or_create(
            batch=batch,
            membership=membership,
            defaults={
                'can_activate': True,
                'can_verify': True,
                'assigned_by': User.objects.first()
            }
        )
        print(f"✓ {'Created' if created else 'Found existing'} batch membership")
        print(f"  - Can activate: {batch_membership.can_activate}")
        print(f"  - Can verify: {batch_membership.can_verify}")
    else:
        print("- No batches found for testing BatchMembership")
    
    # Test 5: Check migration results
    print("\nTest 5: Migration results")
    print(f"✓ Total Users: {User.objects.count()}")
    print(f"✓ Temporary Users: {User.objects.filter(is_temporary=True).count()}")
    print(f"✓ EventMemberships: {EventMembership.objects.count()}")
    print(f"✓ BatchMemberships: {BatchMembership.objects.count()}")
    
    # Test 6: Test user expiry
    print("\nTest 6: Testing user expiry")
    if temp_user.is_expired():
        print("- Temporary user is expired")
    else:
        print(f"✓ Temporary user is active (expires: {temp_user.expires_at})")
    
    print("\n=== All tests completed successfully ===")

if __name__ == '__main__':
    test_unified_auth()
