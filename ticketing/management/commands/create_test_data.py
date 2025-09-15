from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from ticketing.models import Event, TicketType, Batch, Ticket

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test data for ticketing system'

    def handle(self, *args, **options):
        # Create or get test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@tamiti.com',
                'first_name': 'Test',
                'last_name': 'User',
                'is_staff': True
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created test user: {user.username}')
        else:
            self.stdout.write(f'Using existing user: {user.username}')

        # Create test events
        event1, created = Event.objects.get_or_create(
            slug='summer-music-festival-2024',
            defaults={
                'name': 'Summer Music Festival 2024',
                'description': 'Annual summer music festival with top artists',
                'date': timezone.now() + timedelta(days=30),
                'venue': 'Central Park Amphitheater',
                'status': 'active',
                'created_by': user
            }
        )
        if created:
            self.stdout.write(f'Created event: {event1.name}')

        event2, created = Event.objects.get_or_create(
            slug='tech-conference-2024',
            defaults={
                'name': 'Tech Conference 2024',
                'description': 'Leading technology conference with industry experts',
                'date': timezone.now() + timedelta(days=45),
                'venue': 'Convention Center Hall A',
                'status': 'active',
                'created_by': user
            }
        )
        if created:
            self.stdout.write(f'Created event: {event2.name}')

        # Create ticket types
        ticket_type1, created = TicketType.objects.get_or_create(
            event=event1,
            name='General Admission',
            defaults={
                'price': 50.00,
                'description': 'General admission to all festival areas',
                'max_quantity': 1000,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created ticket type: {ticket_type1.name}')

        ticket_type2, created = TicketType.objects.get_or_create(
            event=event1,
            name='VIP',
            defaults={
                'price': 150.00,
                'description': 'VIP access with premium amenities',
                'max_quantity': 200,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created ticket type: {ticket_type2.name}')

        ticket_type3, created = TicketType.objects.get_or_create(
            event=event2,
            name='Standard',
            defaults={
                'price': 200.00,
                'description': 'Standard conference access',
                'max_quantity': 500,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created ticket type: {ticket_type3.name}')

        # Create test batches
        batch1, created = Batch.objects.get_or_create(
            event=event1,
            quantity=100,
            defaults={
                'created_by': user,
                'status': 'active',
                'layout_columns': 5,
                'layout_rows': 20,
                'qr_size': 25,
                'include_short_code': True
            }
        )
        if created:
            self.stdout.write(f'Created batch: {batch1.batch_number}')

        batch2, created = Batch.objects.get_or_create(
            event=event2,
            quantity=50,
            defaults={
                'created_by': user,
                'status': 'active',
                'layout_columns': 5,
                'layout_rows': 10,
                'qr_size': 25,
                'include_short_code': True
            }
        )
        if created:
            self.stdout.write(f'Created batch: {batch2.batch_number}')

        # Create some sample tickets for the batches
        if batch1.tickets.count() == 0:
            for i in range(10):  # Create 10 sample tickets
                ticket = Ticket.objects.create(batch=batch1)
                if i < 5:  # Activate first 5 tickets
                    ticket.status = 'activated'
                    ticket.buyer_name = f'Test Buyer {i+1}'
                    ticket.buyer_phone = f'+123456789{i}'
                    ticket.buyer_email = f'buyer{i+1}@example.com'
                    ticket.ticket_type = ticket_type1
                    ticket.activated_at = timezone.now()
                    ticket.activated_by = user
                    ticket.save()
                if i < 2:  # Scan first 2 tickets
                    ticket.status = 'scanned'
                    ticket.scanned_at = timezone.now()
                    ticket.scanned_by = user
                    ticket.gate = 'Main Entrance'
                    ticket.save()
            self.stdout.write(f'Created 10 sample tickets for {batch1.batch_number}')

        if batch2.tickets.count() == 0:
            for i in range(5):  # Create 5 sample tickets
                ticket = Ticket.objects.create(batch=batch2)
                if i < 3:  # Activate first 3 tickets
                    ticket.status = 'activated'
                    ticket.buyer_name = f'Conference Attendee {i+1}'
                    ticket.buyer_phone = f'+987654321{i}'
                    ticket.buyer_email = f'attendee{i+1}@example.com'
                    ticket.ticket_type = ticket_type3
                    ticket.activated_at = timezone.now()
                    ticket.activated_by = user
                    ticket.save()
            self.stdout.write(f'Created 5 sample tickets for {batch2.batch_number}')

        self.stdout.write(
            self.style.SUCCESS('Successfully created test data for ticketing system!')
        )
        self.stdout.write(f'Test user credentials: username=testuser, password=testpass123')
