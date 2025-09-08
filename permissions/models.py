from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from core.models import BaseModel
from users.models import User


class PermissionAction(models.TextChoices):
    """Available permission actions"""
    CREATE = 'create', 'Create'
    READ = 'read', 'Read'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    LIST = 'list', 'List'


class PermissionType(models.TextChoices):
    """Types of permissions"""
    ALLOW = 'allow', 'Allow'
    DENY = 'deny', 'Deny'


class PermissionScope(models.TextChoices):
    """Scope of permissions"""
    GLOBAL = 'global', 'Global'
    OBJECT = 'object', 'Object-specific'
    FIELD = 'field', 'Field-specific'


class Permission(BaseModel):
    """
    Flexible permission system that supports:
    - User and group-based permissions
    - Allow/deny permissions with deny taking precedence
    - Global, object-specific, and field-specific permissions
    - Content type based permissions for any model
    """
    
    # Permission details
    name = models.CharField(max_length=255, help_text="Human-readable permission name")
    description = models.TextField(blank=True, help_text="Description of what this permission allows/denies")
    
    # Permission configuration
    action = models.CharField(max_length=20, choices=PermissionAction.choices)
    permission_type = models.CharField(max_length=10, choices=PermissionType.choices, default=PermissionType.ALLOW)
    scope = models.CharField(max_length=20, choices=PermissionScope.choices, default=PermissionScope.GLOBAL)
    
    # Target content type (what model this permission applies to)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='custom_permissions')
    
    # Object-specific permissions (optional)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Field-specific permissions (optional)
    field_name = models.CharField(max_length=100, blank=True, help_text="Specific field name for field-level permissions")
    
    # Assignment
    users = models.ManyToManyField(User, blank=True, related_name='custom_permissions')
    groups = models.ManyToManyField(Group, blank=True, related_name='custom_permissions')
    
    # Conditions (optional JSON field for complex conditions)
    conditions = models.JSONField(default=dict, blank=True, help_text="Additional conditions for permission evaluation")
    
    # Priority for conflict resolution (higher number = higher priority)
    priority = models.IntegerField(default=0, help_text="Priority for permission resolution (higher wins)")
    
    # Active status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'permissions_permission'
        indexes = [
            models.Index(fields=['content_type', 'action']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['permission_type', 'priority']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['-priority', '-created_at']
    
    def clean(self):
        """Validate permission configuration"""
        if self.scope == PermissionScope.OBJECT and not self.object_id:
            raise ValidationError("Object ID is required for object-specific permissions")
        
        if self.scope == PermissionScope.FIELD and not self.field_name:
            raise ValidationError("Field name is required for field-specific permissions")
        
        if self.scope == PermissionScope.GLOBAL and (self.object_id or self.field_name):
            raise ValidationError("Global permissions cannot have object_id or field_name")
    
    def __str__(self):
        scope_str = ""
        if self.scope == PermissionScope.OBJECT and self.object_id:
            scope_str = f" (Object: {self.object_id})"
        elif self.scope == PermissionScope.FIELD and self.field_name:
            scope_str = f" (Field: {self.field_name})"
        
        return f"{self.permission_type.title()}: {self.action} on {self.content_type}{scope_str}"


class PermissionGroup(BaseModel):
    """
    Permission groups for easier management of related permissions
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name='permission_groups')
    
    # Assignment
    users = models.ManyToManyField(User, blank=True, related_name='permission_groups')
    groups = models.ManyToManyField(Group, blank=True, related_name='permission_groups')
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'permissions_permission_group'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class UserPermissionCache(BaseModel):
    """
    Cache for computed user permissions to improve performance
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permission_cache')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='permission_cache_entries')
    object_id = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=PermissionAction.choices)
    field_name = models.CharField(max_length=100, blank=True)
    
    # Cached result
    has_permission = models.BooleanField()
    cache_expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'permissions_user_permission_cache'
        unique_together = [
            ('user', 'content_type', 'object_id', 'action', 'field_name')
        ]
        indexes = [
            models.Index(fields=['user', 'content_type', 'action']),
            models.Index(fields=['cache_expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.action} on {self.content_type} - {self.has_permission}"


class PermissionLog(BaseModel):
    """
    Audit log for permission checks and changes
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permission_logs')
    action = models.CharField(max_length=20, choices=PermissionAction.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='permission_log_entries')
    object_id = models.PositiveIntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    
    # Result
    permission_granted = models.BooleanField()
    permissions_applied = models.JSONField(default=list, help_text="List of permission IDs that were evaluated")
    
    # Context
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'permissions_permission_log'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['content_type', 'action']),
            models.Index(fields=['permission_granted']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.action} on {self.content_type} - {'Granted' if self.permission_granted else 'Denied'}"
