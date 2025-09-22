from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import json

from .models import (
    Event, EventMembership, BatchMembership,
    TicketType, Batch, Ticket, ScanLog, BatchExport, TemporaryUser,
)
from django.contrib.auth import get_user_model

User = get_user_model()
from .serializers import (
    EventSerializer, TicketTypeSerializer, BatchSerializer, BatchCreateSerializer,
    TicketSerializer, TicketActivateSerializer, TicketVerifySerializer,
    ScanResultSerializer, ScanLogSerializer, BatchExportSerializer,
    BatchStatsSerializer, EventStatsSerializer, TemporaryUserSerializer,
    TemporaryUserCreateSerializer, TemporaryUserLoginSerializer, UserSerializer
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
                Q(memberships__user=self.request.user, memberships__is_active=True)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        # SECURITY FIX: Replace dead code with intended rule - any authenticated user may create an event
        # The EventSerializer doesn't supply an event field, so the previous code was unreachable
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
        """Get or add event managers using new EventMembership system"""
        event = self.get_object()
        
        # Check if user is event owner or has permission
        if not (request.user == event.created_by or request.user.is_staff):
            return Response(
                {'error': 'Only event owners can manage event managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.method == 'GET':
            memberships = EventMembership.objects.filter(event=event, is_active=True).select_related('user', 'invited_by')
            serializer = EventMembershipSerializer(memberships, many=True)
            return Response({'results': serializer.data})
        
        elif request.method == 'POST':
            # Use EventMembershipSerializer for creating new memberships
            serializer = EventMembershipSerializer(data=request.data)
            if serializer.is_valid():
                # Set the event and invited_by fields
                serializer.validated_data['event'] = event
                serializer.validated_data['invited_by'] = request.user
                
                # Convert permissions list to dict format
                permissions = serializer.validated_data.get('permissions', {})
                if isinstance(permissions, list):
                    permissions_dict = {}
                    for perm in permissions:
                        permissions_dict[perm] = True
                    serializer.validated_data['permissions'] = permissions_dict
                
                membership = serializer.save()
                return Response({
                    'success': True,
                    'membership': EventMembershipSerializer(membership).data,
                    'message': 'Event manager added successfully'
                })
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='managers/(?P<manager_id>[^/.]+)')
    def remove_manager(self, request, pk=None, manager_id=None):
        """Remove an event manager using EventMembership"""
        event = self.get_object()
        
        # Check if user is event owner or has permission
        if not (request.user == event.created_by or request.user.is_staff):
            return Response(
                {'error': 'Only event owners can manage event managers'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            membership = EventMembership.objects.get(
                id=manager_id, 
                event=event, 
                is_active=True
            )
            
            # Prevent removing the owner
            if membership.role == 'owner':
                return Response(
                    {'error': 'Cannot remove event owner'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            membership.is_active = False
            membership.save()
            
            return Response({'message': 'Manager removed successfully'})
            
        except EventMembership.DoesNotExist:
            return Response(
                {'error': 'Manager not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get', 'post'], url_path='batch-managers')
    def batch_managers(self, request, pk=None):
        """Get or add batch managers using new BatchMembership system"""
        event = self.get_object()
        
        # Check if user is event owner or owner manager
        is_owner = request.user == event.created_by
        is_owner_manager = EventMembership.objects.filter(
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
            batch_memberships = BatchMembership.objects.filter(
                batch__event=event
            ).select_related('batch', 'membership__user', 'assigned_by')
            serializer = BatchMembershipSerializer(batch_memberships, many=True)
            return Response({'results': serializer.data})
        
        elif request.method == 'POST':
            serializer = BatchMembershipSerializer(data=request.data)
            if serializer.is_valid():
                # Set the assigned_by field
                serializer.validated_data['assigned_by'] = request.user
                
                batch_membership = serializer.save()
                return Response({
                    'success': True,
                    'batch_membership': BatchMembershipSerializer(batch_membership).data,
                    'message': 'Batch manager assigned successfully'
                })
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch', 'delete'], url_path='batch-managers/(?P<batch_manager_id>[^/.]+)')
    def manage_batch_manager(self, request, pk=None, batch_manager_id=None):
        """Update or remove a batch manager using BatchMembership"""
        event = self.get_object()
        
        # Check if user is event owner or owner manager
        is_owner = request.user == event.created_by
        is_owner_manager = EventMembership.objects.filter(
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
            batch_membership = BatchMembership.objects.get(
                id=batch_manager_id,
                batch__event=event
            )
        except BatchMembership.DoesNotExist:
            return Response(
                {'error': 'Batch manager not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'PATCH':
            # Update batch membership permissions
            can_activate = request.data.get('can_activate', batch_membership.can_activate)
            can_verify = request.data.get('can_verify', batch_membership.can_verify)
            
            batch_membership.can_activate = can_activate
            batch_membership.can_verify = can_verify
            batch_membership.save()
            
            serializer = BatchMembershipSerializer(batch_membership)
            return Response(serializer.data)
        
        elif request.method == 'DELETE':
            # Remove batch membership
            batch_membership.delete()
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
        
        # Filter by permissions (non-admin users see only batches for events they own/manage or batches they manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(event__created_by=self.request.user) |
                Q(event__memberships__user=self.request.user, event__memberships__is_active=True) |
                Q(batch_memberships__membership__user=self.request.user, batch_memberships__is_active=True)
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
                not EventMembership.objects.filter(
                    event=event, 
                    user=request.user, 
                    is_active=True,
                    permissions__create_batches=True
                ).exists()):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to create batches for this event")
        
        # Create the batch
        batch = serializer.save()
        
        # Use BatchSerializer for response to avoid PrimaryKeyRelatedField issues
        response_serializer = BatchSerializer(batch)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def check_batch_permission(self, batch, user, required_permission=None):
        """Check if user has permission to perform actions on this batch"""
        if user.is_staff:
            return True
        
        # Check if user is event owner
        if batch.event.created_by == user:
            return True
        
        # Check if user is event member with appropriate permissions
        event_membership = EventMembership.objects.filter(
            event=batch.event,
            user=user,
            is_active=True
        ).first()
        
        permission_key_map = {
            'can_activate': 'activate_tickets',
            'can_verify': 'verify_tickets',
            'void_batches': 'void_batches',
            'create_batches': 'create_batches',
        }
        if event_membership and required_permission:
            lookup_key = permission_key_map.get(required_permission, required_permission)
            return event_membership.permissions.get(lookup_key, False)
        elif event_membership:
            return True
        
        # Check if user is batch member with appropriate permissions
        batch_membership = BatchMembership.objects.filter(
            batch=batch,
            membership__user=user,
            is_active=True
        ).first()
        
        if batch_membership:
            if required_permission == 'can_activate':
                return batch_membership.can_activate
            elif required_permission == 'can_verify':
                return batch_membership.can_verify
            else:
                return True  # Basic access
        
        return False

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void a batch and all its tickets"""
        batch = self.get_object()
        
        # Check permissions - SECURITY FIX: Use correct permission key
        if not self.check_batch_permission(batch, request.user, 'void_batches'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to void this batch")
        
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


class TicketViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing tickets"""
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'batch']
    search_fields = ['short_code', 'buyer_name', 'buyer_phone', 'buyer_email']
    ordering_fields = ['created_at', 'short_code']
    ordering = ['-created_at']
    
    def _check_batch_permission(self, batch, user, required_permission=None):
        """Check if user has permission to perform actions on this batch"""
        if user.is_staff:
            return True
        
        # Check if user is event owner
        if batch.event.created_by == user:
            return True
        
        # Check if user is event member with appropriate permissions
        event_membership = EventMembership.objects.filter(
            event=batch.event,
            user=user,
            is_active=True
        ).first()
        
        permission_key_map = {
            'can_activate': 'activate_tickets',
            'can_verify': 'verify_tickets',
            'void_batches': 'void_batches',
            'create_batches': 'create_batches',
        }
        if event_membership and required_permission:
            lookup_key = permission_key_map.get(required_permission, required_permission)
            return event_membership.permissions.get(lookup_key, False)
        elif event_membership:
            return True
        
        # Check if user is batch member with appropriate permissions
        batch_membership = BatchMembership.objects.filter(
            batch=batch,
            membership__user=user,
            is_active=True
        ).first()
        
        if batch_membership:
            if required_permission == 'can_activate':
                return batch_membership.can_activate
            elif required_permission == 'can_verify':
                return batch_membership.can_verify
            else:
                return True  # Basic access
        
        return False
    
    def get_permissions(self):
        """Allow public access for single-ticket retrievals."""
        if getattr(self, "action", None) == "retrieve":
            return [AllowAny()]
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'batch__event', 'activated_by', 'scanned_by', 'ticket_type'
        )

        # Anonymous users can retrieve a single ticket shared via link
        if getattr(self, "action", None) == "retrieve" and not self.request.user.is_authenticated:
            return queryset.order_by('short_code')

        # Filter by batch
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # SECURITY FIX: Filter by permissions (non-admin users see only tickets for events they own/manage or batches they manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(batch__created_by=self.request.user) |
                Q(batch__event__created_by=self.request.user) |
                Q(batch__event__memberships__user=self.request.user, batch__event__memberships__is_active=True) |
                Q(batch__batch_memberships__membership__user=self.request.user, batch__batch_memberships__is_active=True)
            ).distinct()
        
        return queryset.order_by('short_code')
    
    @action(detail=False, methods=['post'])
    def activate(self, request):
        """Activate a ticket by QR code"""
        from rest_framework.exceptions import PermissionDenied
        
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
            
            # Check if user has permission to activate tickets for this batch
            if not self._check_batch_permission(ticket.batch, request.user, 'can_activate'):
                scan_log.result = 'permission_denied'
                scan_log.error_message = 'No permission to activate tickets for this batch'
                scan_log.save()
                
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to activate tickets for this batch")
            
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
            
            # Provide more specific error message based on whether event filtering was applied
            if event_id:
                error_message = 'Code is not in the system or not part of the selected event'
            else:
                error_message = 'QR code not found in system'
            
            return Response({
                'success': False,
                'error': error_message,
                'error_type': 'not_found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except PermissionDenied:
            # Re-raise PermissionDenied to be handled by DRF
            raise
        except Exception as e:
            scan_log.result = 'error'
            scan_log.error_message = str(e)
            scan_log.save()
            
            logger.error(f"Ticket verification error: {e}")
            return Response({
                'success': False,
                'error': 'System error during verification. Please try again.',
                'error_type': 'system_error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify/scan a ticket for entry"""
        from rest_framework.exceptions import PermissionDenied
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
            
            # Check if user has permission to verify tickets for this batch
            if not self._check_batch_permission(ticket.batch, request.user, 'can_verify'):
                scan_log.result = 'permission_denied'
                scan_log.error_message = 'No permission to verify tickets for this batch'
                scan_log.save()
                
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You don't have permission to verify tickets for this batch")
            
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
        
        except PermissionDenied:
            # Re-raise PermissionDenied to be handled by DRF
            raise
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
        
        # Filter by event if provided
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(ticket__batch__event_id=event_id)
        
        # Filter by batch if provided
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(ticket__batch_id=batch_id)
            
        # Filter by ticket if provided
        ticket_id = self.request.query_params.get('ticket')
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        
        # Filter by scan result if provided
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.select_related('ticket', 'user').order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get scan history summary statistics"""
        queryset = self.get_queryset()
        
        # Get summary statistics
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        summary = {
            'total_scans': queryset.count(),
            'successful_scans': queryset.filter(result='success').count(),
            'failed_scans': queryset.filter(result__in=['error', 'invalid', 'duplicate']).count(),
            'today_scans': queryset.filter(created_at__date=today).count(),
            'yesterday_scans': queryset.filter(created_at__date=yesterday).count(),
            'week_scans': queryset.filter(created_at__date__gte=week_ago).count(),
            'by_result': dict(queryset.values('result').annotate(count=Count('result')).values_list('result', 'count')),
            'by_gate': dict(queryset.exclude(gate__isnull=True).exclude(gate='').values('gate').annotate(count=Count('gate')).values_list('gate', 'count')),
            'recent_activity': list(queryset[:10].values(
                'id', 'created_at', 'result', 'gate', 'ticket__short_code', 'user__username'
            ))
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get detailed analytics for scan history"""
        queryset = self.get_queryset()
        
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta, datetime
        import json
        
        # Time-based analytics
        now = timezone.now()
        
        # Hourly breakdown for last 24 hours
        hourly_data = []
        for i in range(24):
            hour_start = now - timedelta(hours=i+1)
            hour_end = now - timedelta(hours=i)
            hour_scans = queryset.filter(
                created_at__gte=hour_start,
                created_at__lt=hour_end
            ).count()
            hourly_data.append({
                'hour': hour_start.strftime('%H:00'),
                'scans': hour_scans
            })
        
        # Daily breakdown for last 30 days
        daily_data = []
        for i in range(30):
            day = (now - timedelta(days=i)).date()
            day_scans = queryset.filter(created_at__date=day)
            daily_data.append({
                'date': day.isoformat(),
                'total': day_scans.count(),
                'successful': day_scans.filter(result='success').count(),
                'failed': day_scans.exclude(result='success').count()
            })
        
        # Error analysis
        error_breakdown = queryset.exclude(result='success').values(
            'result', 'error_message'
        ).annotate(count=Count('id')).order_by('-count')[:20]
        
        analytics = {
            'hourly_breakdown': list(reversed(hourly_data)),
            'daily_breakdown': list(reversed(daily_data)),
            'error_breakdown': list(error_breakdown),
            'peak_hours': queryset.extra(
                select={'hour': "EXTRACT(hour FROM created_at)"}
            ).values('hour').annotate(count=Count('id')).order_by('-count')[:5],
            'busiest_gates': queryset.exclude(gate__isnull=True).exclude(gate='').values(
                'gate'
            ).annotate(count=Count('id')).order_by('-count')[:10]
        }
        
        return Response(analytics)


class TicketingUsersViewSet(viewsets.ViewSet):
    """App-specific ViewSet for users and temporary users (for UserSelect component)"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get combined list of users and temporary users for this app"""
        users_data = []
        
        # Get filtering parameters
        search = request.query_params.get('search')
        is_temporary = request.query_params.get('is_temporary')
        created_for_event = request.query_params.get('created_for_event')
        
        # If filtering for temporary users only, skip regular users
        if is_temporary and is_temporary.lower() == 'true':
            pass  # Skip regular users section
        else:
            # Get regular users based on permissions
            if request.user.is_staff:
                # Staff can see all active users
                users = User.objects.filter(is_active=True, is_temporary=False)
            else:
                # Non-staff can only see themselves
                users = User.objects.filter(id=request.user.id, is_active=True, is_temporary=False)
            
            # Add search functionality for users
            if search:
                users = users.filter(
                    Q(username__icontains=search) |
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )
        
            # Serialize regular users
            for user in users.order_by('username'):
                name = f"{user.first_name} {user.last_name}".strip() if user.first_name and user.last_name else user.username
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'name': name,
                    'type': 'regular',
                    'is_active': user.is_active,
                })
        
        # Get temporary users (now unified in User model)
        temp_users = User.objects.filter(is_temporary=True)

        # Filter by event if specified
        if created_for_event:
            temp_users = temp_users.filter(created_for_event_id=created_for_event)

        # Filter temporary users based on permissions
        if not request.user.is_staff:
            # Non-staff can only see temp users for events they manage
            managed_events = Event.objects.filter(
                Q(created_by=request.user) |
                Q(memberships__user=request.user, memberships__is_active=True)
            ).distinct()
            temp_users = temp_users.filter(created_for_event__in=managed_events)

        # Add search functionality for temporary users
        if search:
            temp_users = temp_users.filter(
                Q(username__icontains=search)
            )

        temp_users = temp_users.select_related('created_for_event')

        # Preload memberships for permissions/role information
        membership_lookup = {}
        temp_user_ids = list(temp_users.values_list('id', flat=True))
        if temp_user_ids:
            memberships = EventMembership.objects.filter(
                user_id__in=temp_user_ids
            ).select_related('event', 'user')
            for membership in memberships:
                key = (membership.user_id, membership.event_id)
                # Prefer active membership for created_for_event
                if key not in membership_lookup or membership.is_active:
                    membership_lookup[key] = membership

        # Serialize temporary users
        for temp_user in temp_users.order_by('username'):
            event = temp_user.created_for_event
            membership = None
            if event:
                membership = membership_lookup.get((temp_user.id, event.id))

            permissions = membership.permissions if membership else {}
            can_activate = permissions.get('activate_tickets', False)
            can_verify = permissions.get('verify_tickets', False)
            can_scan = permissions.get('scan_tickets', False) or permissions.get('verify_tickets', False)
            full_name = f"{temp_user.first_name} {temp_user.last_name}".strip()

            users_data.append({
                'id': temp_user.id,
                'username': temp_user.username,
                'email': temp_user.email,
                'name': full_name or temp_user.username,
                'event_id': event.id if event else None,
                'event_name': event.name if event else 'N/A',
                'role': membership.role if membership else temp_user.role,
                'type': 'temporary',
                'is_active': temp_user.is_active,
                'is_expired': temp_user.is_expired(),
                'expires_at': temp_user.expires_at,
                'last_login': temp_user.last_login,
                'login_count': getattr(temp_user, 'login_count', None),
                'permissions': permissions,
                'can_activate': can_activate,
                'can_verify': can_verify,
                'can_scan': can_scan,
                'membership_id': membership.id if membership else None,
                'membership_role': membership.role if membership else None,
            })

        return Response({'results': users_data})


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


class TemporaryUserViewSet(viewsets.ModelViewSet):
    """DEPRECATED: ViewSet for managing temporary users - use unified User model instead"""
    queryset = TemporaryUser.objects.all()
    serializer_class = TemporaryUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event', 'role', 'is_active']
    search_fields = ['username']
    ordering_fields = ['username', 'created_at', 'expires_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter temporary users based on user permissions"""
        queryset = super().get_queryset()
        
        # Staff can see all temporary users
        if self.request.user.is_staff:
            return queryset
        
        # Non-staff can only see temporary users for events they manage
        managed_events = Event.objects.filter(
            Q(created_by=self.request.user) |
            Q(memberships__user=self.request.user, memberships__is_active=True)
        ).distinct()
        
        return queryset.filter(event__in=managed_events)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TemporaryUserCreateSerializer
        return TemporaryUserSerializer
    
    def perform_create(self, serializer):
        # SECURITY FIX: Check event-level authorization
        event = serializer.validated_data.get('event')
        if not event:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Event is required")
        
        # Only event owner or staff can Create temporary Users
        from .viewsets import can_manage_event
        if not can_manage_event(self.request.user, event):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only event owners can Create temporary Users")
        
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a temporary user"""
        temp_user = self.get_object()
        temp_user.is_active = False
        temp_user.save()
        
        return Response({
            'success': True,
            'message': 'Temporary user deactivated successfully'
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a temporary user"""
        temp_user = self.get_object()
        
        if temp_user.is_expired():
            return Response({
                'success': False,
                'error': 'Cannot activate expired temporary user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        temp_user.is_active = True
        temp_user.save()
        
        return Response({
            'success': True,
            'message': 'Temporary user activated successfully'
        })


# Temporary user login endpoint removed - all users now use standard JWT authentication


class TemporaryUserCreateViewSet(viewsets.ModelViewSet):
    """ViewSet for creating temporary users with proper permission handling"""
    serializer_class = TemporaryUserCreateSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['post']  # Only allow creation
    
    def get_queryset(self):
        # This ViewSet is only for creation, no listing
        return User.objects.none()
    
    def get_serializer_class(self):
        return TemporaryUserCreateSerializer
    
    def perform_create(self, serializer):
        # Permission checking is handled in the serializer
        # The serializer creates both User and EventMembership
        user = serializer.save()
        
        # Add generated password to response if available
        if hasattr(user, '_generated_password') and user._generated_password:
            self.generated_password = user._generated_password
    
    def create(self, request, *args, **kwargs):
        """Override create to include generated password in response"""
        response = super().create(request, *args, **kwargs)
        
        # Add generated password to response if available
        if hasattr(self, 'generated_password'):
            response.data['generated_password'] = self.generated_password
            
        return response
# Temporary users are now regular User objects with is_temporary=True
