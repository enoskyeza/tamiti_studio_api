from typing import List, Optional, Dict, Any, Union
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from django.db.models import Q, QuerySet
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from django.db import transaction
from django.db.utils import OperationalError
import time
import logging
from users.models import User
from .models import (
    Permission, PermissionGroup, UserPermissionCache, PermissionLog,
    PermissionAction, PermissionType, PermissionScope
)


class PermissionService:
    """
    Core service for permission evaluation and management
    """
    
    def __init__(self, cache_timeout: int = 300):  # 5 minutes default cache
        self.cache_timeout = cache_timeout
    
    def has_permission(
        self,
        user: User,
        action: str,
        content_type: Union[ContentType, str],
        obj: Optional[Any] = None,
        field_name: Optional[str] = None,
        use_cache: bool = True,
        log_check: bool = True
    ) -> bool:
        """
        Check if user has permission for a specific action
        
        Args:
            user: User to check permissions for
            action: Action to check (create, read, update, delete, list)
            content_type: ContentType instance or "app_label.model" string
            obj: Optional object instance for object-specific permissions
            field_name: Optional field name for field-specific permissions
            use_cache: Whether to use cached results
            log_check: Whether to log this permission check
        
        Returns:
            bool: True if permission is granted, False otherwise
        """
        
        # Convert string content_type to ContentType instance
        if isinstance(content_type, str):
            try:
                app_label, model = content_type.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model)
            except (ValueError, ContentType.DoesNotExist):
                return False
        
        object_id = obj.pk if obj else None
        
        # Check cache first
        if use_cache:
            cached_result = self._get_cached_permission(
                user, content_type, object_id, action, field_name
            )
            if cached_result is not None:
                if log_check:
                    self._log_permission_check(
                        user, action, content_type, object_id, field_name, cached_result, []
                    )
                return cached_result
        
        # Evaluate permissions
        result, applied_permissions = self._evaluate_permissions(
            user, action, content_type, object_id, field_name
        )
        
        # Cache result
        if use_cache:
            self._cache_permission_result(
                user, content_type, object_id, action, field_name, result
            )
        
        # Log permission check
        if log_check:
            self._log_permission_check(
                user, action, content_type, object_id, field_name, result, applied_permissions
            )
        
        return result
    
    def _evaluate_permissions(
        self,
        user: User,
        action: str,
        content_type: ContentType,
        object_id: Optional[int],
        field_name: Optional[str]
    ) -> tuple[bool, List[int]]:
        """
        Evaluate all applicable permissions for a user
        
        Returns:
            tuple: (has_permission, list_of_applied_permission_ids)
        """
        
        # Get all applicable permissions
        permissions = self._get_applicable_permissions(
            user, action, content_type, object_id, field_name
        )
        
        if not permissions:
            # No specific permissions found, default to deny
            return False, []
        
        applied_permission_ids = [p.id for p in permissions]
        
        # Evaluate permissions (DENY takes precedence over ALLOW)
        # Sort by priority (highest first), then by type (DENY first)
        sorted_permissions = sorted(
            permissions,
            key=lambda p: (-p.priority, p.permission_type == PermissionType.ALLOW)
        )
        
        for permission in sorted_permissions:
            if permission.permission_type == PermissionType.DENY:
                return False, applied_permission_ids
            elif permission.permission_type == PermissionType.ALLOW:
                return True, applied_permission_ids
        
        return False, applied_permission_ids
    
    def _get_applicable_permissions(
        self,
        user: User,
        action: str,
        content_type: ContentType,
        object_id: Optional[int],
        field_name: Optional[str]
    ) -> List[Permission]:
        """
        Get all permissions applicable to this user and context
        """
        
        # Base query for active permissions matching action and content_type
        base_query = Permission.objects.filter(
            is_active=True,
            action=action,
            content_type=content_type
        )
        
        # Get user's groups
        user_groups = user.groups.all()
        
        # Query for permissions assigned to user or their groups
        permission_query = Q(users=user) | Q(groups__in=user_groups)
        
        # Also check permission groups
        permission_group_query = Q(
            permission_groups__users=user
        ) | Q(
            permission_groups__groups__in=user_groups
        )
        
        permissions = base_query.filter(
            permission_query | permission_group_query
        ).distinct()
        
        # Filter by scope
        applicable_permissions = []
        
        for permission in permissions:
            if self._is_permission_applicable(permission, object_id, field_name):
                applicable_permissions.append(permission)
        
        return applicable_permissions
    
    def _is_permission_applicable(
        self,
        permission: Permission,
        object_id: Optional[int],
        field_name: Optional[str]
    ) -> bool:
        """
        Check if a permission is applicable to the current context
        """
        
        if permission.scope == PermissionScope.GLOBAL:
            return True
        
        elif permission.scope == PermissionScope.OBJECT:
            return permission.object_id == object_id
        
        elif permission.scope == PermissionScope.FIELD:
            return permission.field_name == field_name
        
        return False
    
    def _get_cached_permission(
        self,
        user: User,
        content_type: ContentType,
        object_id: Optional[int],
        action: str,
        field_name: Optional[str]
    ) -> Optional[bool]:
        """
        Get cached permission result if available and not expired
        """
        
        try:
            cache_entry = UserPermissionCache.objects.get(
                user=user,
                content_type=content_type,
                object_id=object_id,
                action=action,
                field_name=field_name or '',
                cache_expires_at__gt=timezone.now()
            )
            return cache_entry.has_permission
        except UserPermissionCache.DoesNotExist:
            return None
    
    def _cache_permission_result(
        self,
        user: User,
        content_type: ContentType,
        object_id: Optional[str],
        action: str,
        field_name: Optional[str],
        result: bool
    ):
        """
        Cache permission result with retry logic for database locks
        """
        
        expires_at = timezone.now() + timedelta(seconds=self.cache_timeout)
        
        # Retry logic for SQLite database locks
        max_retries = 3
        retry_delay = 0.1  # Start with 100ms delay
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    UserPermissionCache.objects.update_or_create(
                        user=user,
                        content_type=content_type,
                        object_id=object_id,
                        action=action,
                        field_name=field_name or '',
                        defaults={
                            'has_permission': result,
                            'cache_expires_at': expires_at
                        }
                    )
                return  # Success, exit the retry loop
                
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    # Wait with exponential backoff before retrying
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    # Log the error but don't fail the permission check
                    logging.warning(f"Failed to cache permission result after {max_retries} attempts: {e}")
                    return
    
    def _log_permission_check(
        self,
        user: User,
        action: str,
        content_type: ContentType,
        object_id: Optional[int],
        field_name: Optional[str],
        result: bool,
        applied_permissions: List[int]
    ):
        """
        Log permission check for audit purposes with retry logic for database locks
        """
        
        # Retry logic for SQLite database locks
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    PermissionLog.objects.create(
                        user=user,
                        action=action,
                        content_type=content_type,
                        object_id=object_id,
                        field_name=field_name or '',
                        permission_granted=result,
                        permissions_applied=applied_permissions
                    )
                return  # Success, exit the retry loop
                
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    # Log the error but don't fail the permission check
                    logging.warning(f"Failed to log permission check after {max_retries} attempts: {e}")
                    return
    
    def clear_user_cache(self, user: User):
        """
        Clear all cached permissions for a user
        """
        UserPermissionCache.objects.filter(user=user).delete()
    
    def clear_cache_for_object(self, content_type: ContentType, object_id: int):
        """
        Clear cached permissions for a specific object
        """
        UserPermissionCache.objects.filter(
            content_type=content_type,
            object_id=object_id
        ).delete()
    
    def get_filtered_queryset(
        self,
        user: User,
        queryset: QuerySet,
        action: str = PermissionAction.READ
    ) -> QuerySet:
        """
        Filter queryset based on user's permissions
        
        Args:
            user: User to check permissions for
            queryset: Base queryset to filter
            action: Action to check permissions for (default: read)
        
        Returns:
            QuerySet: Filtered queryset containing only objects user has permission for
        """
        
        model = queryset.model
        content_type = ContentType.objects.get_for_model(model)
        
        # Get all object-specific permissions for this user and model
        permissions = self._get_applicable_permissions(
            user, action, content_type, None, None
        )
        
        # If user has global ALLOW permission, return full queryset
        global_allows = [p for p in permissions if p.scope == PermissionScope.GLOBAL and p.permission_type == PermissionType.ALLOW]
        global_denies = [p for p in permissions if p.scope == PermissionScope.GLOBAL and p.permission_type == PermissionType.DENY]
        
        # If there's a global deny with higher priority than any global allow, return empty
        if global_denies:
            highest_deny_priority = max(p.priority for p in global_denies)
            highest_allow_priority = max((p.priority for p in global_allows), default=-1)
            
            if highest_deny_priority >= highest_allow_priority:
                return queryset.none()
        
        # If there's a global allow, return full queryset (unless overridden by object-specific denies)
        if global_allows:
            object_denies = [p for p in permissions if p.scope == PermissionScope.OBJECT and p.permission_type == PermissionType.DENY]
            if object_denies:
                denied_object_ids = [p.object_id for p in object_denies]
                return queryset.exclude(pk__in=denied_object_ids)
            return queryset
        
        # No global permissions, check object-specific permissions
        object_allows = [p for p in permissions if p.scope == PermissionScope.OBJECT and p.permission_type == PermissionType.ALLOW]
        
        if object_allows:
            allowed_object_ids = [p.object_id for p in object_allows]
            return queryset.filter(pk__in=allowed_object_ids)
        
        # No applicable permissions found, return empty queryset
        return queryset.none()


# Global permission service instance
permission_service = PermissionService()
