from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.http import Http404
import logging

from .models import (
    Event, EventManager, BatchManager,
    TicketType, Batch, Ticket, ScanLog, BatchExport, TemporaryUser,
)
from django.contrib.auth import get_user_model

User = get_user_model()
from .serializers import (
    EventSerializer, EventManagerSerializer, EventManagerCreateSerializer,
    BatchManagerSerializer, BatchManagerCreateSerializer,
    TicketTypeSerializer, BatchSerializer, BatchCreateSerializer,
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
                email = serializer.validated_data.get('email')
                user_id = serializer.validated_data.get('user_id')
                is_temporary = serializer.validated_data.get('is_temporary', False)
                role = serializer.validated_data['role']
                permissions = serializer.validated_data.get('permissions', [])
                
                print(f"Received data: user_id={user_id}, is_temporary={is_temporary}, role={role}")
                
                # Smart user resolution with fallback logic
                user = None
                temp_user = None
                final_is_temporary = is_temporary
                
                if user_id and user_id != 'undefined':
                    # Handle prefixed temporary user IDs
                    if str(user_id).startswith('temp_'):
                        temp_id_str = user_id.replace('temp_', '')
                        if temp_id_str and temp_id_str != 'undefined':
                            try:
                                temp_id = int(temp_id_str)
                                temp_user = TemporaryUser.objects.get(id=temp_id)
                                final_is_temporary = True
                            except (ValueError, TemporaryUser.DoesNotExist):
                                # Fallback: try as regular user ID
                                try:
                                    user = User.objects.get(id=temp_id_str)
                                    final_is_temporary = False
                                except User.DoesNotExist:
                                    return Response(
                                        {'error': f'No user found with ID {temp_id_str}'}, 
                                        status=status.HTTP_404_NOT_FOUND
                                    )
                    else:
                        # Handle regular user ID or ambiguous ID
                        try:
                            numeric_id = int(user_id)
                            if is_temporary:
                                # Try temporary user first
                                try:
                                    temp_user = TemporaryUser.objects.get(id=numeric_id)
                                    final_is_temporary = True
                                except TemporaryUser.DoesNotExist:
                                    # Fallback to regular user
                                    try:
                                        user = User.objects.get(id=numeric_id)
                                        final_is_temporary = False
                                    except User.DoesNotExist:
                                        return Response(
                                            {'error': f'No user found with ID {numeric_id}'}, 
                                            status=status.HTTP_404_NOT_FOUND
                                        )
                            else:
                                # Try regular user first
                                try:
                                    user = User.objects.get(id=numeric_id)
                                    final_is_temporary = False
                                except User.DoesNotExist:
                                    # Fallback to temporary user
                                    try:
                                        temp_user = TemporaryUser.objects.get(id=numeric_id)
                                        final_is_temporary = True
                                    except TemporaryUser.DoesNotExist:
                                        return Response(
                                            {'error': f'No user found with ID {numeric_id}'}, 
                                            status=status.HTTP_404_NOT_FOUND
                                        )
                        except ValueError:
                            return Response(
                                {'error': 'Invalid user_id format'}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )
                
                elif email:
                    # Email lookup (only for regular users)
                    try:
                        user = User.objects.get(email=email)
                        final_is_temporary = False
                    except User.DoesNotExist:
                        return Response(
                            {'error': 'User with this email does not exist'}, 
                            status=status.HTTP_404_NOT_FOUND
                        )
                
                # Check for existing manager
                existing_manager = None
                if final_is_temporary and temp_user:
                    existing_manager = EventManager.objects.filter(
                        event=event, temp_user=temp_user, is_temporary=True
                    ).first()
                elif not final_is_temporary and user:
                    existing_manager = EventManager.objects.filter(
                        event=event, user=user, is_temporary=False
                    ).first()
                
                if existing_manager:
                    return Response(
                        {'error': 'User is already a manager for this event'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate that we have a user before creating
                if not user and not temp_user:
                    return Response(
                        {'error': 'No valid user found to assign as manager'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                print(f"Creating EventManager with: user={user}, temp_user={temp_user}, is_temporary={final_is_temporary}")
                
                # Create event manager
                event_manager = EventManager.objects.create(
                    event=event,
                    user=user if not final_is_temporary else None,
                    temp_user=temp_user if final_is_temporary else None,
                    is_temporary=final_is_temporary,
                    role=role,
                    permissions=permissions,
                    assigned_by=request.user
                )
                
                response_serializer = EventManagerSerializer(event_manager)
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
        
        # Filter by permissions (non-admin users see only batches for events they own/manage or batches they manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(event__created_by=self.request.user) |
                Q(event__managers__user=self.request.user, event__managers__is_active=True) |
                Q(batch_managers__manager=self.request.user, batch_managers__is_active=True)
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
    
    def check_batch_permission(self, batch, user, required_permission=None):
        """Check if user has permission to perform actions on this batch"""
        if user.is_staff:
            return True
        
        # Check if user is event owner
        if batch.event.created_by == user:
            return True
        
        # Check if user is event manager with appropriate permissions
        event_manager = EventManager.objects.filter(
            event=batch.event,
            user=user,
            is_active=True
        ).first()
        
        if event_manager and required_permission:
            return required_permission in event_manager.permissions
        elif event_manager:
            return True
        
        # Check if user is batch manager with appropriate permissions
        batch_manager = BatchManager.objects.filter(
            batch=batch,
            manager=user,
            is_active=True
        ).first()
        
        if batch_manager:
            if required_permission == 'can_activate':
                return batch_manager.can_activate
            elif required_permission == 'can_verify':
                return batch_manager.can_verify
            else:
                return True  # Basic access
        
        return False

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void a batch and all its tickets"""
        batch = self.get_object()
        
        # Check permissions
        if not self.check_batch_permission(batch, request.user, 'manage_batches'):
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
        
        # Check if user is event manager with appropriate permissions
        event_manager = EventManager.objects.filter(
            event=batch.event,
            user=user,
            is_active=True
        ).first()
        
        if event_manager and required_permission:
            return required_permission in event_manager.permissions
        elif event_manager:
            return True
        
        # Check if user is batch manager with appropriate permissions
        batch_manager = BatchManager.objects.filter(
            batch=batch,
            manager=user,
            is_active=True
        ).first()
        
        if batch_manager:
            if required_permission == 'can_activate':
                return batch_manager.can_activate
            elif required_permission == 'can_verify':
                return batch_manager.can_verify
            else:
                return True  # Basic access
        
        return False
    
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
            
            # Check if user has permission to activate tickets for this batch
            if not self._check_batch_permission(ticket.batch, request.user, 'can_activate'):
                scan_log.result = 'error'
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
            
            # Check if user has permission to verify tickets for this batch
            if not self._check_batch_permission(ticket.batch, request.user, 'can_verify'):
                scan_log.result = 'error'
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
        
        # Get regular users based on permissions
        if request.user.is_staff:
            # Staff can see all active users
            users = User.objects.filter(is_active=True)
        else:
            # Non-staff can only see themselves
            users = User.objects.filter(id=request.user.id, is_active=True)
        
        # Add search functionality for users
        search = request.query_params.get('search')
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
                'type': 'regular'
            })
        
        # Get temporary users (event managers can see temp users for their events)
        temp_users = TemporaryUser.objects.filter(is_active=True)
        
        # Filter temporary users based on permissions
        if not request.user.is_staff:
            # Non-staff can only see temp users for events they manage
            managed_events = Event.objects.filter(
                Q(created_by=request.user) |
                Q(managers__user=request.user, managers__is_active=True)
            ).distinct()
            temp_users = temp_users.filter(event__in=managed_events)
        
        # Add search functionality for temporary users
        if search:
            temp_users = temp_users.filter(
                Q(username__icontains=search)
            )
        
        # Serialize temporary users
        for temp_user in temp_users.order_by('username'):
            users_data.append({
                'id': f"temp_{temp_user.id}",
                'username': temp_user.username,
                'email': f"{temp_user.username}@temp.local",
                'name': temp_user.username,
                'type': 'temporary',
                'event_id': temp_user.event.id,
                'event_name': temp_user.event.name
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
    """ViewSet for managing temporary users"""
    queryset = TemporaryUser.objects.all()
    serializer_class = TemporaryUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['event', 'role', 'is_active']
    search_fields = ['username']
    ordering_fields = ['created_at', 'expires_at', 'username']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by permissions (non-admin users see only temp users for events they own/manage)
        if not self.request.user.is_staff:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(event__created_by=self.request.user) |
                Q(event__managers__user=self.request.user, event__managers__is_active=True)
            ).distinct()
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TemporaryUserCreateSerializer
        return TemporaryUserSerializer
    
    def perform_create(self, serializer):
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


@action(detail=False, methods=['post'], permission_classes=[])
def temp_user_login(request):
    """Login endpoint for temporary users"""
    serializer = TemporaryUserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']
    event_id = serializer.validated_data.get('event_id')
    
    try:
        # Find temporary user
        temp_user_query = TemporaryUser.objects.filter(username=username, is_active=True)
        if event_id:
            temp_user_query = temp_user_query.filter(event_id=event_id)
        
        temp_user = temp_user_query.first()
        
        if not temp_user:
            return Response({
                'success': False,
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if temp_user.is_expired():
            return Response({
                'success': False,
                'error': 'Account has expired'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not temp_user.check_password(password):
            return Response({
                'success': False,
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Record login
        temp_user.record_login()
        
        # Create a simple session token (in production, use JWT or similar)
        from django.contrib.auth.tokens import default_token_generator
        token = default_token_generator.make_token(temp_user)
        
        return Response({
            'success': True,
            'user': TemporaryUserSerializer(temp_user).data,
            'token': token,
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Temporary user login error: {str(e)}")
        return Response({
            'success': False,
            'error': 'Login failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
