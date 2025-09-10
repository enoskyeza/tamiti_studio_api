from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import generics, viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiParameter
from users.models import User
from .models import Permission, PermissionGroup, PermissionLog
from .serializers import (
    PermissionSerializer, PermissionCreateSerializer, PermissionGroupSerializer,
    PermissionLogSerializer, PermissionCheckSerializer, PermissionCheckResponseSerializer,
    BulkPermissionAssignSerializer, UserPermissionSummarySerializer,
    ContentTypePermissionSerializer
)
from .services import permission_service


class PermissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing permissions
    """
    queryset = Permission.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PermissionCreateSerializer
        return PermissionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            try:
                app_label, model = content_type.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=ct)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by permission type
        permission_type = self.request.query_params.get('permission_type')
        if permission_type:
            queryset = queryset.filter(permission_type=permission_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.select_related('content_type').prefetch_related('users', 'groups')
    
    @extend_schema(
        request=BulkPermissionAssignSerializer,
        responses={200: {'description': 'Permissions assigned/removed successfully'}}
    )
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """Bulk assign or remove permissions to/from users and groups"""
        serializer = BulkPermissionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        permission_ids = serializer.validated_data['permission_ids']
        user_ids = serializer.validated_data.get('user_ids', [])
        group_ids = serializer.validated_data.get('group_ids', [])
        action = serializer.validated_data['action']
        
        permissions = Permission.objects.filter(id__in=permission_ids)
        users = User.objects.filter(id__in=user_ids) if user_ids else []
        groups = Group.objects.filter(id__in=group_ids) if group_ids else []
        
        for permission in permissions:
            if action == 'assign':
                permission.users.add(*users)
                permission.groups.add(*groups)
            else:  # remove
                permission.users.remove(*users)
                permission.groups.remove(*groups)
        
        # Clear cache for affected users
        for user in users:
            permission_service.clear_user_cache(user)
        
        return Response({'message': f'Permissions {action}ed successfully'})


class PermissionGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing permission groups
    """
    queryset = PermissionGroup.objects.all()
    serializer_class = PermissionGroupSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.prefetch_related('permissions', 'users', 'groups')


class PermissionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing permission logs (read-only)
    """
    queryset = PermissionLog.objects.all()
    serializer_class = PermissionLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            try:
                app_label, model = content_type.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                queryset = queryset.filter(content_type=ct)
            except (ValueError, ContentType.DoesNotExist):
                pass
        
        # Filter by permission granted
        permission_granted = self.request.query_params.get('permission_granted')
        if permission_granted is not None:
            queryset = queryset.filter(permission_granted=permission_granted.lower() == 'true')
        
        return queryset.select_related('user', 'content_type')


@extend_schema(
    request=PermissionCheckSerializer,
    responses=PermissionCheckResponseSerializer
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_permission(request):
    """
    Check if current user has specific permission
    """
    serializer = PermissionCheckSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    action = serializer.validated_data['action']
    content_type = serializer.validated_data['content_type']
    object_id = serializer.validated_data.get('object_id')
    field_name = serializer.validated_data.get('field_name', '')
    
    # Get object if object_id provided
    obj = None
    if object_id:
        try:
            app_label, model = content_type.split('.')
            ct = ContentType.objects.get(app_label=app_label, model=model)
            model_class = ct.model_class()
            obj = model_class.objects.get(pk=object_id)
        except:
            pass
    
    has_perm = permission_service.has_permission(
        user=request.user,
        action=action,
        content_type=content_type,
        obj=obj,
        field_name=field_name
    )
    
    # Get applied permissions for response
    applied_permissions = []
    # This would require modifying the service to return applied permissions
    # For now, return empty list
    
    response_data = {
        'has_permission': has_perm,
        'action': action,
        'content_type': content_type,
        'object_id': object_id,
        'field_name': field_name,
        'applied_permissions': applied_permissions
    }
    
    return Response(response_data)


@extend_schema(
    parameters=[
        OpenApiParameter(name="user_id", type=int, location=OpenApiParameter.QUERY, description="User ID to get permissions for")
    ],
    responses=UserPermissionSummarySerializer
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def user_permissions(request):
    """
    Get comprehensive permission summary for a user
    """
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = get_object_or_404(User, id=user_id)
    
    # Get direct permissions
    direct_permissions = Permission.objects.filter(
        users=user,
        is_active=True
    ).select_related('content_type')
    
    # Get permissions through groups
    group_permissions = Permission.objects.filter(
        groups__in=user.groups.all(),
        is_active=True
    ).select_related('content_type')
    
    # Get permissions through permission groups
    permission_group_permissions = Permission.objects.filter(
        permission_groups__users=user,
        permission_groups__is_active=True,
        is_active=True
    ).select_related('content_type')
    
    # Get permission groups
    permission_groups = PermissionGroup.objects.filter(
        users=user,
        is_active=True
    )
    
    # Serialize data
    permissions_data = []
    all_permissions = (direct_permissions | group_permissions | permission_group_permissions).distinct()
    
    for perm in all_permissions:
        permissions_data.append({
            'id': perm.id,
            'name': perm.name,
            'action': perm.action,
            'permission_type': perm.permission_type,
            'scope': perm.scope,
            'content_type': f"{perm.content_type.app_label}.{perm.content_type.model}",
            'object_id': perm.object_id,
            'field_name': perm.field_name,
            'priority': perm.priority
        })
    
    permission_groups_data = []
    for pg in permission_groups:
        permission_groups_data.append({
            'id': pg.id,
            'name': pg.name,
            'description': pg.description
        })
    
    response_data = {
        'user_id': user.id,
        'username': user.username,
        'full_name': user.get_full_name(),
        'permissions': permissions_data,
        'permission_groups': permission_groups_data
    }
    
    return Response(response_data)


@extend_schema(
    responses=ContentTypePermissionSerializer(many=True)
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def content_type_permissions(request):
    """
    Get permission overview by content type
    """
    content_types = ContentType.objects.all()
    data = []
    
    for ct in content_types:
        permissions = Permission.objects.filter(content_type=ct, is_active=True)
        
        if permissions.exists():
            permissions_data = []
            for perm in permissions:
                permissions_data.append({
                    'id': perm.id,
                    'name': perm.name,
                    'action': perm.action,
                    'permission_type': perm.permission_type,
                    'scope': perm.scope,
                    'user_count': perm.users.count(),
                    'group_count': perm.groups.count()
                })
            
            total_users = User.objects.filter(
                custom_permissions__content_type=ct,
                custom_permissions__is_active=True
            ).distinct().count()
            
            total_groups = Group.objects.filter(
                custom_permissions__content_type=ct,
                custom_permissions__is_active=True
            ).distinct().count()
            
            data.append({
                'content_type': f"{ct.app_label}.{ct.model}",
                'model_name': ct.model,
                'permissions': permissions_data,
                'user_count': total_users,
                'group_count': total_groups
            })
    
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def clear_permission_cache(request):
    """
    Clear permission cache for specific user or all users
    """
    user_id = request.data.get('user_id')
    
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            permission_service.clear_user_cache(user)
            return Response({'message': f'Cache cleared for user {user.username}'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        # Clear all cache
        from .models import UserPermissionCache
        UserPermissionCache.objects.all().delete()
        return Response({'message': 'All permission cache cleared'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def permission_stats(request):
    """
    Get permission system statistics
    """
    stats = {
        'total_permissions': Permission.objects.filter(is_active=True).count(),
        'total_permission_groups': PermissionGroup.objects.filter(is_active=True).count(),
        'total_users_with_permissions': User.objects.filter(
            custom_permissions__is_active=True
        ).distinct().count(),
        'total_groups_with_permissions': Group.objects.filter(
            custom_permissions__is_active=True
        ).distinct().count(),
        'permission_checks_today': PermissionLog.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'denied_permissions_today': PermissionLog.objects.filter(
            created_at__date=timezone.now().date(),
            permission_granted=False
        ).count()
    }
    
    return Response(stats)
