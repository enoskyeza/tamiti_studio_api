from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.http import Http404
import logging

from .models import Event, EventManager, BatchManager, TicketType, Batch, Ticket, ScanLog, BatchExport
from .serializers import (
    EventSerializer, EventManagerSerializer, EventManagerCreateSerializer,
    BatchManagerSerializer, BatchManagerCreateSerializer,
    TicketTypeSerializer, BatchSerializer, BatchCreateSerializer,
    TicketSerializer, TicketActivateSerializer, TicketVerifySerializer,
    ScanResultSerializer, ScanLogSerializer, BatchExportSerializer,
    BatchStatsSerializer, EventStatsSerializer
)

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class EventViewSet(viewsets.ModelViewSet):
    """ViewSet for managing events"""
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Event.objects.all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user permissions (non-admin users see only their events or events they manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(managers__user=self.request.user, managers__is_active=True)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        # Check if user has permission to create batches for this event
        event = serializer.validated_data.get('event')
        if event and not self.request.user.is_staff:
            # Check if user is event owner or has create_batches permission
            if (event.created_by != self.request.user and 
                not EventManager.objects.filter(
                    event=event, 
                    user=self.request.user, 
                    is_active=True,
                    permissions__contains=['create_batches']
                ).exists()):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to create batches for this event")
        
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get statistics for a specific event"""
        event = self.get_object()
        tickets = Ticket.objects.filter(batch__event=event)
        
        total_tickets = tickets.count()
        activated_tickets = tickets.filter(status__in=['activated', 'scanned']).count()
        scanned_tickets = tickets.filter(status='scanned').count()
        
        activation_rate = (activated_tickets / total_tickets * 100) if total_tickets > 0 else 0
        scan_rate = (scanned_tickets / total_tickets * 100) if total_tickets > 0 else 0
        
        stats_data = {
            'event': EventSerializer(event).data,
            'total_tickets': total_tickets,
            'activated_tickets': activated_tickets,
            'scanned_tickets': scanned_tickets,
            'activation_rate': round(activation_rate, 2),
            'scan_rate': round(scan_rate, 2)
        }
        
        serializer = EventStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'post'])
    def managers(self, request, pk=None):
        """Get or add event managers"""
        event = self.get_object()
        
        # Check if user is event owner or has permission
        if not (request.user == event.created_by or request.user.is_staff):
            return Response(
                {'error': 'Only event owners can manage event managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'GET':
            managers = EventManager.objects.filter(event=event, is_active=True)
            serializer = EventManagerSerializer(managers, many=True)
            return Response({'results': serializer.data})
        
        elif request.method == 'POST':
            serializer = EventManagerCreateSerializer(data=request.data)
            if serializer.is_valid():
                email = serializer.validated_data['email']
                role = serializer.validated_data['role']
                permissions = serializer.validated_data.get('permissions', [])
                
                # Find user by email
                try:
                    from django.contrib.auth.models import User
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'User with this email does not exist'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if user is already a manager
                if EventManager.objects.filter(event=event, user=user, is_active=True).exists():
                    return Response(
                        {'error': 'User is already a manager for this event'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create event manager
                manager = EventManager.objects.create(
                    event=event,
                    user=user,
                    role=role,
                    permissions=permissions,
                    assigned_by=request.user
                )
                
                response_serializer = EventManagerSerializer(manager)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='managers/(?P<manager_id>[^/.]+)')
    def remove_manager(self, request, pk=None, manager_id=None):
        """Remove an event manager"""
        event = self.get_object()
        
        # Check if user is event owner or has permission
        if not (request.user == event.created_by or request.user.is_staff):
            return Response(
                {'error': 'Only event owners can manage event managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            manager = EventManager.objects.get(
                id=manager_id, 
                event=event, 
                is_active=True
            )
            
            # Prevent removing the owner
            if manager.role == 'owner':
                return Response(
                    {'error': 'Cannot remove event owner'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            manager.is_active = False
            manager.save()
            
            return Response({'message': 'Manager removed successfully'})
            
        except EventManager.DoesNotExist:
            return Response(
                {'error': 'Manager not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get', 'post'], url_path='batch-managers')
    def batch_managers(self, request, pk=None):
        """Get or add batch managers"""
        event = self.get_object()
        
        # Check if user is event owner or owner manager
        is_owner = request.user == event.created_by
        is_owner_manager = EventManager.objects.filter(
            event=event, 
            user=request.user, 
            role='owner', 
            is_active=True
        ).exists()
        
        if not (is_owner or is_owner_manager or request.user.is_staff):
            return Response(
                {'error': 'Only event owners and owner managers can manage batch managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'GET':
            batch_managers = BatchManager.objects.filter(
                batch__event=event
            ).select_related('batch', 'manager__user', 'assigned_by')
            serializer = BatchManagerSerializer(batch_managers, many=True)
            return Response({'results': serializer.data})
        
        elif request.method == 'POST':
            serializer = BatchManagerCreateSerializer(data=request.data)
            if serializer.is_valid():
                batch_id = serializer.validated_data['batch_id']
                manager_id = serializer.validated_data['manager_id']
                can_activate = serializer.validated_data['can_activate']
                can_verify = serializer.validated_data['can_verify']
                
                # Verify batch belongs to this event
                try:
                    batch = Batch.objects.get(id=batch_id, event=event)
                except Batch.DoesNotExist:
                    return Response(
                        {'error': 'Batch not found for this event'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Verify manager exists and is active for this event
                try:
                    manager = EventManager.objects.get(
                        id=manager_id, 
                        event=event, 
                        is_active=True
                    )
                except EventManager.DoesNotExist:
                    return Response(
                        {'error': 'Manager not found for this event'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if batch manager already exists
                if BatchManager.objects.filter(batch=batch, manager=manager).exists():
                    return Response(
                        {'error': 'Manager is already assigned to this batch'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create batch manager
                batch_manager = BatchManager.objects.create(
                    batch=batch,
                    manager=manager,
                    can_activate=can_activate,
                    can_verify=can_verify,
                    assigned_by=request.user
                )
                
                response_serializer = BatchManagerSerializer(batch_manager)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch', 'delete'], url_path='batch-managers/(?P<batch_manager_id>[^/.]+)')
    def manage_batch_manager(self, request, pk=None, batch_manager_id=None):
        """Update or remove a batch manager"""
        event = self.get_object()
        
        # Check if user is event owner or owner manager
        is_owner = request.user == event.created_by
        is_owner_manager = EventManager.objects.filter(
            event=event, 
            user=request.user, 
            role='owner', 
            is_active=True
        ).exists()
        
        if not (is_owner or is_owner_manager or request.user.is_staff):
            return Response(
                {'error': 'Only event owners and owner managers can manage batch managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            batch_manager = BatchManager.objects.get(
                id=batch_manager_id,
                batch__event=event
            )
        except BatchManager.DoesNotExist:
            return Response(
                {'error': 'Batch manager not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'PATCH':
            # Update batch manager permissions
            can_activate = request.data.get('can_activate', batch_manager.can_activate)
            can_verify = request.data.get('can_verify', batch_manager.can_verify)
            
            batch_manager.can_activate = can_activate
            batch_manager.can_verify = can_verify
            batch_manager.save()
            
            serializer = BatchManagerSerializer(batch_manager)
            return Response(serializer.data)
        
        elif request.method == 'DELETE':
            # Remove batch manager
            batch_manager.delete()
            return Response({'message': 'Batch manager removed successfully'})


class TicketTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket types"""
    queryset = TicketType.objects.all()
    serializer_class = TicketTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = TicketType.objects.all()
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        return queryset.filter(is_active=True).order_by('price')


class BatchViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket batches"""
    queryset = Batch.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BatchCreateSerializer
        return BatchSerializer
    
    def get_queryset(self):
        queryset = Batch.objects.select_related('event', 'created_by').prefetch_related('tickets')
        
        # Filter by event
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by permissions (non-admin users see only batches for events they own/manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(event__created_by=self.request.user) |
                Q(event__managers__user=self.request.user, event__managers__is_active=True)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        # Use BatchCreateSerializer for input validation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user has permission to create batches for this event
        event = serializer.validated_data.get('event')
        if event and not request.user.is_staff:
            # Check if user is event owner or has create_batches permission
            if (event.created_by != request.user and 
                not EventManager.objects.filter(
                    event=event, 
                    user=request.user, 
                    is_active=True,
                    permissions__contains=['create_batches']
                ).exists()):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to create batches for this event")
        
        # Create the batch
        batch = serializer.save()
        
        # Use BatchSerializer for response to avoid PrimaryKeyRelatedField issues
        response_serializer = BatchSerializer(batch)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void a batch and all its tickets"""
        batch = self.get_object()
        
        if batch.status == 'void':
            return Response(
                {'error': 'Batch is already voided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        
        with transaction.atomic():
            # Void the batch
            batch.status = 'void'
            batch.voided_at = timezone.now()
            batch.voided_by = request.user
            batch.void_reason = reason
            batch.save()
            
            # Void all unused tickets in the batch
            batch.tickets.filter(status='unused').update(status='void')
        
        return Response({'message': 'Batch voided successfully'})
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        """Get paginated tickets for a batch"""
        batch = self.get_object()
        tickets = batch.tickets.all().order_by('short_code')
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            tickets = tickets.filter(status=status_filter)
        
        # Search functionality
        search = request.query_params.get('search', '')
        if search:
            from django.db.models import Q
            tickets = tickets.filter(
                Q(short_code__icontains=search) |
                Q(buyer_name__icontains=search) |
                Q(buyer_phone__icontains=search) |
                Q(buyer_email__icontains=search)
            )
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_tickets = tickets[start:end]
        total = tickets.count()
        has_more = end < total
        
        serializer = TicketSerializer(paginated_tickets, many=True)
        
        return Response({
            'tickets': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_more': has_more
        })
    
    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        """Export batch as PDF, CSV, or images"""
        batch = self.get_object()
        export_type = request.data.get('export_type', 'pdf')
        
        if export_type not in ['pdf', 'csv', 'png', 'svg']:
            return Response(
                {'error': 'Invalid export type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create export record
        export_record = BatchExport.objects.create(
            batch=batch,
            export_type=export_type,
            exported_by=request.user
        )
        
        # TODO: Implement actual file generation
        # For now, return the export record
        serializer = BatchExportSerializer(export_record)
        return Response(serializer.data)


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing tickets"""
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'batch__event', 'activated_by', 'scanned_by', 'ticket_type'
        )
        
        # Filter by batch
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('short_code')
    
    @action(detail=False, methods=['post'])
    def activate(self, request):
        """Activate a ticket by QR code"""
        serializer = TicketActivateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        qr_code = serializer.validated_data['qr_code']
        buyer_info = serializer.validated_data.get('buyer_info', {})
        event_id = serializer.validated_data.get('event_id')
        
        # Log the scan attempt
        scan_log = ScanLog(
            qr_code=qr_code,
            scan_type='activate',
            user=request.user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        try:
            # Find the ticket with optional event filtering
            ticket_query = Ticket.objects.select_related('batch__event')
            if event_id:
                ticket_query = ticket_query.filter(batch__event_id=event_id)
            
            # Try to find ticket by QR code first, then by short code
            try:
                ticket = ticket_query.get(qr_code=qr_code)
            except Ticket.DoesNotExist:
                # If not found by QR code, try by short code (for manual entry)
                ticket = ticket_query.get(short_code=qr_code.upper())
            scan_log.ticket = ticket
            
            if ticket.status != 'unused':
                scan_log.result = 'error'
                scan_log.error_message = f'Ticket already {ticket.status}'
                scan_log.save()
                
                error_messages = {
                    'activated': 'Ticket is already activated',
                    'scanned': 'Ticket is already activated and scanned',
                    'void': 'Ticket has been voided and cannot be activated'
                }
                
                return Response({
                    'success': False,
                    'error': error_messages.get(ticket.status, f'Ticket is already {ticket.status}'),
                    'error_type': 'already_processed',
                    'current_status': ticket.status
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Activate the ticket
            with transaction.atomic():
                ticket.activate(request.user, buyer_info)
                scan_log.result = 'success'
                scan_log.save()
            
            # Return success response
            result_data = {
                'success': True,
                'ticket': TicketSerializer(ticket).data
            }
            
            return Response(result_data)
            
        except Ticket.DoesNotExist:
            scan_log.result = 'invalid'
            scan_log.error_message = 'Ticket not found'
            scan_log.save()
            
            return Response({
                'success': False,
                'error': 'QR code not found in system',
                'error_type': 'not_found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            scan_log.result = 'error'
            scan_log.error_message = str(e)
            scan_log.save()
            
            logger.error(f"Ticket activation error: {e}")
            return Response({
                'success': False,
                'error': 'System error during activation. Please try again.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify/scan a ticket for entry"""
        serializer = TicketVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        qr_code = serializer.validated_data['qr_code']
        gate = serializer.validated_data.get('gate', '')
        event_id = serializer.validated_data.get('event_id')
        
        # Log the scan attempt
        scan_log = ScanLog(
            qr_code=qr_code,
            scan_type='verify',
            user=request.user,
            gate=gate,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        try:
            # Find the ticket with optional event filtering
            ticket_query = Ticket.objects.select_related('batch__event', 'activated_by', 'scanned_by')
            if event_id:
                ticket_query = ticket_query.filter(batch__event_id=event_id)
            
            # Try to find ticket by QR code first, then by short code
            try:
                ticket = ticket_query.get(qr_code=qr_code)
            except Ticket.DoesNotExist:
                # If not found by QR code, try by short code (for manual entry)
                ticket = ticket_query.get(short_code=qr_code.upper())
            scan_log.ticket = ticket
            
            if ticket.status == 'unused':
                scan_log.result = 'error'
                scan_log.error_message = 'Ticket not activated'
                scan_log.save()
                
                return Response({
                    'success': False,
                    'error': 'Invalid or unactivated ticket'
                })
            
            elif ticket.status == 'void':
                scan_log.result = 'error'
                scan_log.error_message = 'Ticket voided'
                scan_log.save()
                
                return Response({
                    'success': False,
                    'error': 'Invalid or voided ticket'
                })
            
            elif ticket.status == 'scanned':
                scan_log.result = 'duplicate'
                scan_log.error_message = 'Already scanned'
                scan_log.save()
                
                return Response({
                    'success': False,
                    'error': 'Already scanned',
                    'duplicateInfo': {
                        'originalScanTime': ticket.scanned_at.isoformat() if ticket.scanned_at else None,
                        'gate': ticket.gate or 'Unknown',
                        'staffName': ticket.scanned_by.username if ticket.scanned_by else 'Unknown'
                    }
                })
            
            # Scan the ticket
            with transaction.atomic():
                ticket.scan(request.user, gate)
                scan_log.result = 'success'
                scan_log.save()
            
            # Return success response with UI-expected format
            ticket_data = TicketSerializer(ticket).data
            result_data = {
                'success': True,
                'ticket': {
                    'id': ticket.id,
                    'shortCode': ticket.short_code,
                    'qr_code': ticket.qr_code,
                    'status': ticket.status,
                    'buyer_info': ticket_data.get('buyer_info'),
                    'batch_number': ticket_data.get('batch_number'),
                    'event_name': ticket_data.get('event_name'),
                    'ticket_type_name': ticket_data.get('ticket_type_name'),
                    'activated_at': ticket.activated_at.isoformat() if ticket.activated_at else None,
                    'activated_by_name': ticket_data.get('activated_by_name'),
                    'scanned_at': ticket.scanned_at.isoformat() if ticket.scanned_at else None,
                    'scanned_by_name': ticket_data.get('scanned_by_name'),
                    'gate': ticket.gate
                }
            }
            
            return Response(result_data)
            
        except Ticket.DoesNotExist:
            scan_log.result = 'invalid'
            scan_log.error_message = 'Ticket not found'
            scan_log.save()
            
            return Response({
                'success': False,
                'error': 'Invalid or unactivated ticket'
            })
        
        except Exception as e:
            scan_log.result = 'error'
            scan_log.error_message = str(e)
            scan_log.save()
            
            logger.error(f"Ticket verification error: {e}")
            return Response({
                'success': False,
                'error': 'Verification failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScanLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing scan logs"""
    queryset = ScanLog.objects.all()
    serializer_class = ScanLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter scan logs with optional parameters"""
        queryset = ScanLog.objects.select_related('user', 'ticket')
        
        # Filter by scan type
        scan_type = self.request.query_params.get('scan_type')
        if scan_type:
            queryset = queryset.filter(scan_type=scan_type)
        
        # Filter by result
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result)
        
        # Filter by user (for non-admin users)
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        
        return queryset.order_by('-created_at')


class DashboardViewSet(viewsets.ViewSet):
    """ViewSet for dashboard statistics"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get overall dashboard statistics"""
        user = request.user
        
        # Base querysets
        if user.is_staff:
            batches = Batch.objects.all()
            tickets = Ticket.objects.all()
        else:
            batches = Batch.objects.filter(created_by=user)
            tickets = Ticket.objects.filter(batch__created_by=user)
        
        # Calculate stats
        total_batches = batches.count()
        total_tickets = tickets.count()
        activated_tickets = tickets.filter(status__in=['activated', 'scanned']).count()
        scanned_tickets = tickets.filter(status='scanned').count()
        unused_tickets = tickets.filter(status='unused').count()
        voided_tickets = tickets.filter(status='void').count()
        
        stats_data = {
            'total_batches': total_batches,
            'total_tickets': total_tickets,
            'activated_tickets': activated_tickets,
            'scanned_tickets': scanned_tickets,
            'unused_tickets': unused_tickets,
            'voided_tickets': voided_tickets
        }
        
        serializer = BatchStatsSerializer(stats_data)
        return Response(serializer.data)
