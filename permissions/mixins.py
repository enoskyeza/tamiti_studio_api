from typing import Optional, Any
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import GenericAPIView
from .services import permission_service
from .models import PermissionAction


class PermissionRequiredMixin:
    """
    Mixin for Django views that require permission checking
    """
    permission_action = None  # Override in subclass
    permission_content_type = None  # Override in subclass or auto-detect from model
    permission_field = None  # Optional field-level permission
    
    def dispatch(self, request, *args, **kwargs):
        if not self.check_permission(request, *args, **kwargs):
            raise PermissionDenied("You don't have permission to perform this action")
        return super().dispatch(request, *args, **kwargs)
    
    def check_permission(self, request, *args, **kwargs) -> bool:
        """
        Check if user has required permission
        """
        if not request.user.is_authenticated:
            return False
        
        action = self.get_permission_action(request, *args, **kwargs)
        content_type = self.get_permission_content_type()
        obj = self.get_permission_object(*args, **kwargs)
        field_name = self.get_permission_field()
        
        return permission_service.has_permission(
            user=request.user,
            action=action,
            content_type=content_type,
            obj=obj,
            field_name=field_name
        )
    
    def get_permission_action(self, request, *args, **kwargs) -> str:
        """
        Get the permission action for this request
        """
        if self.permission_action:
            return self.permission_action
        
        # Auto-detect based on HTTP method
        method_action_map = {
            'GET': PermissionAction.READ,
            'POST': PermissionAction.CREATE,
            'PUT': PermissionAction.UPDATE,
            'PATCH': PermissionAction.UPDATE,
            'DELETE': PermissionAction.DELETE,
        }
        
        return method_action_map.get(request.method, PermissionAction.READ)
    
    def get_permission_content_type(self):
        """
        Get the content type for permission checking
        """
        if self.permission_content_type:
            return self.permission_content_type
        
        # Auto-detect from model if available
        if hasattr(self, 'model') and self.model:
            return ContentType.objects.get_for_model(self.model)
        
        if hasattr(self, 'get_queryset'):
            queryset = self.get_queryset()
            if queryset is not None:
                return ContentType.objects.get_for_model(queryset.model)
        
        raise NotImplementedError("Must specify permission_content_type or have a model/queryset")
    
    def get_permission_object(self, *args, **kwargs) -> Optional[Any]:
        """
        Get the object for object-specific permission checking
        """
        # Try to get object from view if it's a detail view
        if hasattr(self, 'get_object'):
            try:
                return self.get_object()
            except:
                pass
        
        return None
    
    def get_permission_field(self) -> Optional[str]:
        """
        Get the field name for field-specific permission checking
        """
        return self.permission_field


class DRFPermissionMixin:
    """
    Mixin for Django REST Framework views with permission checking
    """
    permission_action_map = {
        'list': PermissionAction.LIST,
        'retrieve': PermissionAction.READ,
        'create': PermissionAction.CREATE,
        'update': PermissionAction.UPDATE,
        'partial_update': PermissionAction.UPDATE,
        'destroy': PermissionAction.DELETE,
    }
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_authenticated:
            return queryset.none()
        
        # Get action for permission checking
        action = self.get_permission_action()
        
        # Filter queryset based on permissions
        return permission_service.get_filtered_queryset(
            user=self.request.user,
            queryset=queryset,
            action=action
        )
    
    def check_object_permissions(self, request, obj):
        """
        Check object-level permissions
        """
        super().check_object_permissions(request, obj)
        
        action = self.get_permission_action()
        content_type = ContentType.objects.get_for_model(obj)
        
        if not permission_service.has_permission(
            user=request.user,
            action=action,
            content_type=content_type,
            obj=obj
        ):
            self.permission_denied(
                request,
                message=f"You don't have permission to {action} this {content_type.model}"
            )
    
    def get_permission_action(self) -> str:
        """
        Get permission action based on DRF action
        """
        if hasattr(self, 'action') and self.action:
            return self.permission_action_map.get(self.action, PermissionAction.READ)
        
        # Fallback to HTTP method mapping
        method_action_map = {
            'GET': PermissionAction.READ,
            'POST': PermissionAction.CREATE,
            'PUT': PermissionAction.UPDATE,
            'PATCH': PermissionAction.UPDATE,
            'DELETE': PermissionAction.DELETE,
        }
        
        return method_action_map.get(self.request.method, PermissionAction.READ)


class CustomPermission(permissions.BasePermission):
    """
    Custom DRF permission class that uses our permission system
    """
    
    def has_permission(self, request: Request, view: GenericAPIView) -> bool:
        """
        Check if user has permission to access this view
        """
        if not request.user.is_authenticated:
            return False
        
        # Get action
        action = self._get_action(request, view)
        
        # Get content type
        content_type = self._get_content_type(view)
        
        if not content_type:
            return True  # Can't check permissions without content type
        
        return permission_service.has_permission(
            user=request.user,
            action=action,
            content_type=content_type
        )
    
    def has_object_permission(self, request: Request, view: GenericAPIView, obj: Any) -> bool:
        """
        Check if user has permission to access this specific object
        """
        if not request.user.is_authenticated:
            return False
        
        action = self._get_action(request, view)
        content_type = ContentType.objects.get_for_model(obj)
        
        return permission_service.has_permission(
            user=request.user,
            action=action,
            content_type=content_type,
            obj=obj
        )
    
    def _get_action(self, request: Request, view: GenericAPIView) -> str:
        """
        Determine the action based on request and view
        """
        if hasattr(view, 'action') and view.action:
            action_map = {
                'list': PermissionAction.LIST,
                'retrieve': PermissionAction.READ,
                'create': PermissionAction.CREATE,
                'update': PermissionAction.UPDATE,
                'partial_update': PermissionAction.UPDATE,
                'destroy': PermissionAction.DELETE,
            }
            return action_map.get(view.action, PermissionAction.READ)
        
        # Fallback to HTTP method
        method_map = {
            'GET': PermissionAction.READ,
            'POST': PermissionAction.CREATE,
            'PUT': PermissionAction.UPDATE,
            'PATCH': PermissionAction.UPDATE,
            'DELETE': PermissionAction.DELETE,
        }
        
        return method_map.get(request.method, PermissionAction.READ)
    
    def _get_content_type(self, view: GenericAPIView) -> Optional[ContentType]:
        """
        Get content type from view
        """
        if hasattr(view, 'queryset') and view.queryset is not None:
            return ContentType.objects.get_for_model(view.queryset.model)
        
        if hasattr(view, 'get_queryset'):
            try:
                queryset = view.get_queryset()
                if queryset is not None:
                    return ContentType.objects.get_for_model(queryset.model)
            except:
                pass
        
        if hasattr(view, 'serializer_class') and view.serializer_class:
            if hasattr(view.serializer_class, 'Meta') and hasattr(view.serializer_class.Meta, 'model'):
                return ContentType.objects.get_for_model(view.serializer_class.Meta.model)
        
        return None


class PermissionFilterMixin:
    """
    Mixin that automatically filters querysets based on permissions
    """
    
    def filter_queryset(self, queryset):
        """
        Filter queryset based on user permissions
        """
        queryset = super().filter_queryset(queryset)
        
        if not self.request.user.is_authenticated:
            return queryset.none()
        
        return permission_service.get_filtered_queryset(
            user=self.request.user,
            queryset=queryset,
            action=PermissionAction.READ
        )


# Convenience classes combining mixins
class PermissionModelViewSet(DRFPermissionMixin, PermissionFilterMixin, ModelViewSet):
    """
    ModelViewSet with automatic permission checking and filtering
    """
    permission_classes = [CustomPermission]


class PermissionGenericAPIView(DRFPermissionMixin, PermissionFilterMixin, GenericAPIView):
    """
    GenericAPIView with automatic permission checking and filtering
    """
    permission_classes = [CustomPermission]
