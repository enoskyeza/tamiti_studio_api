from functools import wraps
from typing import Optional, Callable, Any
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from .services import permission_service
from .models import PermissionAction


def permission_required(
    action: str,
    content_type: Optional[str] = None,
    field_name: Optional[str] = None,
    raise_exception: bool = True
):
    """
    Decorator for function-based views that require specific permissions
    
    Args:
        action: Permission action (create, read, update, delete, list)
        content_type: Content type as "app_label.model" string (optional, auto-detect from view)
        field_name: Field name for field-specific permissions (optional)
        raise_exception: Whether to raise PermissionDenied or return False
    
    Usage:
        @permission_required('read', 'tasks.task')
        def my_view(request):
            # View logic here
            pass
    """
    
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Authentication required")
                return False
            
            # Determine content type
            ct = content_type
            if not ct and hasattr(view_func, '_content_type'):
                ct = view_func._content_type
            
            # Get object if available (for object-specific permissions)
            obj = None
            if 'pk' in kwargs or 'id' in kwargs:
                obj_id = kwargs.get('pk') or kwargs.get('id')
                if ct and obj_id:
                    try:
                        app_label, model = ct.split('.')
                        ct_obj = ContentType.objects.get(app_label=app_label, model=model)
                        model_class = ct_obj.model_class()
                        obj = model_class.objects.get(pk=obj_id)
                    except:
                        obj = None
            
            has_perm = permission_service.has_permission(
                user=request.user,
                action=action,
                content_type=ct,
                obj=obj,
                field_name=field_name
            )
            
            if not has_perm:
                if raise_exception:
                    raise PermissionDenied(f"You don't have permission to {action}")
                return False
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def model_permission_required(model_class, action: str, field_name: Optional[str] = None):
    """
    Decorator that automatically determines content type from model class
    
    Args:
        model_class: Django model class
        action: Permission action
        field_name: Optional field name for field-specific permissions
    
    Usage:
        @model_permission_required(Task, 'create')
        def create_task_view(request):
            # View logic here
            pass
    """
    content_type = ContentType.objects.get_for_model(model_class)
    content_type_str = f"{content_type.app_label}.{content_type.model}"
    
    return permission_required(action, content_type_str, field_name)


def check_permission(
    user,
    action: str,
    content_type: str,
    obj: Optional[Any] = None,
    field_name: Optional[str] = None
) -> bool:
    """
    Utility function to check permissions programmatically
    
    Args:
        user: User instance
        action: Permission action
        content_type: Content type as "app_label.model"
        obj: Optional object instance
        field_name: Optional field name
    
    Returns:
        bool: True if permission granted, False otherwise
    
    Usage:
        if check_permission(request.user, 'update', 'tasks.task', task_instance):
            # User can update this task
            pass
    """
    if not user.is_authenticated:
        return False
    
    return permission_service.has_permission(
        user=user,
        action=action,
        content_type=content_type,
        obj=obj,
        field_name=field_name
    )


def require_any_permission(*permission_specs):
    """
    Decorator that requires ANY of the specified permissions (OR logic)
    
    Args:
        permission_specs: Tuples of (action, content_type, field_name)
    
    Usage:
        @require_any_permission(
            ('read', 'tasks.task'),
            ('update', 'tasks.task'),
        )
        def task_view(request, pk):
            # User needs either read OR update permission
            pass
    """
    
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get object if available
            obj = None
            if 'pk' in kwargs or 'id' in kwargs:
                obj_id = kwargs.get('pk') or kwargs.get('id')
                # Try to get object for first permission spec
                if permission_specs and obj_id:
                    try:
                        action, content_type = permission_specs[0][:2]
                        app_label, model = content_type.split('.')
                        ct_obj = ContentType.objects.get(app_label=app_label, model=model)
                        model_class = ct_obj.model_class()
                        obj = model_class.objects.get(pk=obj_id)
                    except:
                        obj = None
            
            # Check each permission spec
            for spec in permission_specs:
                action = spec[0]
                content_type = spec[1]
                field_name = spec[2] if len(spec) > 2 else None
                
                if permission_service.has_permission(
                    user=request.user,
                    action=action,
                    content_type=content_type,
                    obj=obj,
                    field_name=field_name
                ):
                    return view_func(request, *args, **kwargs)
            
            raise PermissionDenied("You don't have any of the required permissions")
        
        return wrapper
    return decorator


def require_all_permissions(*permission_specs):
    """
    Decorator that requires ALL of the specified permissions (AND logic)
    
    Args:
        permission_specs: Tuples of (action, content_type, field_name)
    
    Usage:
        @require_all_permissions(
            ('read', 'tasks.task'),
            ('update', 'tasks.task'),
        )
        def task_edit_view(request, pk):
            # User needs both read AND update permission
            pass
    """
    
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> Any:
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get object if available
            obj = None
            if 'pk' in kwargs or 'id' in kwargs:
                obj_id = kwargs.get('pk') or kwargs.get('id')
                # Try to get object for first permission spec
                if permission_specs and obj_id:
                    try:
                        action, content_type = permission_specs[0][:2]
                        app_label, model = content_type.split('.')
                        ct_obj = ContentType.objects.get(app_label=app_label, model=model)
                        model_class = ct_obj.model_class()
                        obj = model_class.objects.get(pk=obj_id)
                    except:
                        obj = None
            
            # Check all permission specs
            for spec in permission_specs:
                action = spec[0]
                content_type = spec[1]
                field_name = spec[2] if len(spec) > 2 else None
                
                if not permission_service.has_permission(
                    user=request.user,
                    action=action,
                    content_type=content_type,
                    obj=obj,
                    field_name=field_name
                ):
                    raise PermissionDenied(f"You don't have permission to {action} {content_type}")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def permission_required_for_field(model_class, field_name: str, action: str = PermissionAction.READ):
    """
    Decorator for field-specific permissions
    
    Args:
        model_class: Django model class
        field_name: Name of the field
        action: Permission action (default: read)
    
    Usage:
        @permission_required_for_field(Task, 'confidential_notes', 'read')
        def get_task_notes(request, pk):
            # User needs read permission for confidential_notes field
            pass
    """
    content_type = ContentType.objects.get_for_model(model_class)
    content_type_str = f"{content_type.app_label}.{content_type.model}"
    
    return permission_required(action, content_type_str, field_name)


class PermissionContext:
    """
    Context manager for temporarily checking permissions
    
    Usage:
        with PermissionContext(user, 'update', 'tasks.task', task_obj) as has_perm:
            if has_perm:
                # User has permission
                task_obj.save()
            else:
                # Handle no permission case
                pass
    """
    
    def __init__(self, user, action: str, content_type: str, obj: Optional[Any] = None, field_name: Optional[str] = None):
        self.user = user
        self.action = action
        self.content_type = content_type
        self.obj = obj
        self.field_name = field_name
        self.has_permission = False
    
    def __enter__(self) -> bool:
        self.has_permission = check_permission(
            self.user, self.action, self.content_type, self.obj, self.field_name
        )
        return self.has_permission
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
