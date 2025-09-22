"""
ViewSets for the new unified membership system
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db import models
from .models import EventMembership, BatchMembership
from .serializers import EventMembershipSerializer, BatchMembershipSerializer

User = get_user_model()


def can_manage_event(user, event):
    """Check if user can manage an event (creator or owner membership)"""
    if user.is_staff:
        return True
    if user == event.created_by:
        return True
    # Check if user has owner role in event memberships
    return EventMembership.objects.filter(
        event=event, 
        user=user, 
        role='owner', 
        is_active=True
    ).exists()


def can_manage_batch(user, batch):
    """Check if user can manage a batch (event owner or has manage_staff permission)"""
    if user.is_staff:
        return True
    if user == batch.event.created_by:
        return True
    # Check if user has owner role or manage_staff permission
    membership = EventMembership.objects.filter(
        event=batch.event, 
        user=user, 
        is_active=True
    ).first()
    if membership:
        return membership.role == 'owner' or membership.has_permission('manage_staff')
    return False


class EventMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for managing event memberships"""
    serializer_class = EventMembershipSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter memberships based on user permissions"""
        queryset = EventMembership.objects.select_related('user', 'event', 'invited_by')
        
        # Filter by event if specified
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Users can only see memberships for events they own or are members of
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                models.Q(event__created_by=self.request.user) |
                models.Q(user=self.request.user)
            )
        
        if self.action in ['list']:
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('role', 'user__username')
    
    def perform_create(self, serializer):
        """Set the invited_by field when creating a membership"""
        # SECURITY FIX: Check that the caller owns the event
        event = serializer.validated_data.get('event')
        if not event:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Event is required")
        
        if not can_manage_event(self.request.user, event):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only event owners can create memberships")
        
        serializer.save(invited_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle membership active status"""
        membership = self.get_object()
        
        # Check permissions
        if not can_manage_event(request.user, membership.event):
            return Response(
                {'error': 'Only event owners can manage memberships'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Prevent deactivating the owner
        if membership.role == 'owner':
            return Response(
                {'error': 'Cannot deactivate event owner'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        membership.is_active = not membership.is_active
        membership.save()
        
        return Response({
            'success': True,
            'is_active': membership.is_active,
            'message': f'Membership {"activated" if membership.is_active else "deactivated"}'
        })


class BatchMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for managing batch memberships"""
    serializer_class = BatchMembershipSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter batch memberships based on user permissions"""
        queryset = BatchMembership.objects.select_related(
            'batch', 'membership__user', 'membership__event', 'assigned_by'
        )
        
        # Filter by batch if specified
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        
        # Filter by event if specified
        event_id = self.request.query_params.get('event')
        if event_id:
            queryset = queryset.filter(batch__event_id=event_id)
        
        # Users can only see batch memberships for events they own or are members of
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                models.Q(batch__event__created_by=self.request.user) |
                models.Q(membership__user=self.request.user)
            )
        
        if self.action in ['list']:
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('batch__batch_number', 'membership__user__username')
    
    def perform_create(self, serializer):
        """Set the assigned_by field when creating a batch membership"""
        # SECURITY FIX: Check that the caller owns the event
        batch = serializer.validated_data.get('batch')
        batch_id = serializer.validated_data.get('batch_id')
        
        # Get batch object if batch_id is provided instead of batch
        if not batch and batch_id:
            from .models import Batch
            try:
                batch = Batch.objects.get(id=batch_id)
            except Batch.DoesNotExist:
                from rest_framework.exceptions import ValidationError
                raise ValidationError("Batch does not exist")
        
        if not batch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Batch is required")
        
        if not can_manage_batch(self.request.user, batch):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only event owners can create batch memberships")
        
        serializer.save(assigned_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def toggle_permissions(self, request, pk=None):
        """Toggle batch membership permissions"""
        batch_membership = self.get_object()
        
        # Check permissions
        if not can_manage_batch(request.user, batch_membership.batch):
            return Response(
                {'error': 'Only event owners can manage batch permissions'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        can_activate = request.data.get('can_activate')
        can_verify = request.data.get('can_verify')
        
        if can_activate is not None:
            batch_membership.can_activate = can_activate
        if can_verify is not None:
            batch_membership.can_verify = can_verify
        
        batch_membership.save()
        
        return Response({
            'success': True,
            'can_activate': batch_membership.can_activate,
            'can_verify': batch_membership.can_verify,
            'message': 'Permissions updated successfully'
        })
