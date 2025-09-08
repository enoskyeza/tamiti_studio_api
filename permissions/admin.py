from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from .models import Permission, PermissionGroup, PermissionLog, UserPermissionCache


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'action', 'permission_type', 'scope', 'content_type_display',
        'object_id', 'field_name', 'priority', 'is_active', 'created_at'
    ]
    list_filter = [
        'action', 'permission_type', 'scope', 'content_type', 'is_active', 'created_at'
    ]
    search_fields = ['name', 'description', 'content_type__model', 'content_type__app_label']
    filter_horizontal = ['users', 'groups']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permission Configuration', {
            'fields': ('action', 'permission_type', 'scope', 'priority')
        }),
        ('Target', {
            'fields': ('content_type', 'object_id', 'field_name')
        }),
        ('Assignment', {
            'fields': ('users', 'groups')
        }),
        ('Advanced', {
            'fields': ('conditions',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def content_type_display(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"
    content_type_display.short_description = 'Content Type'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')


@admin.register(PermissionGroup)
class PermissionGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'permission_count', 'user_count', 'group_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['permissions', 'users', 'groups']
    readonly_fields = ['created_at', 'updated_at']
    
    def permission_count(self, obj):
        return obj.permissions.count()
    permission_count.short_description = 'Permissions'
    
    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Users'
    
    def group_count(self, obj):
        return obj.groups.count()
    group_count.short_description = 'Groups'


@admin.register(PermissionLog)
class PermissionLogAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'action', 'content_type_display', 'object_id',
        'permission_granted', 'created_at'
    ]
    list_filter = [
        'action', 'permission_granted', 'content_type', 'created_at'
    ]
    search_fields = ['user__username', 'user__email', 'content_type__model']
    readonly_fields = [
        'user', 'action', 'content_type', 'object_id', 'field_name',
        'permission_granted', 'permissions_applied', 'request_ip',
        'user_agent', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    def content_type_display(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"
    content_type_display.short_description = 'Content Type'
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be modified
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(UserPermissionCache)
class UserPermissionCacheAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'action', 'content_type_display', 'object_id',
        'has_permission', 'cache_expires_at', 'created_at'
    ]
    list_filter = [
        'action', 'has_permission', 'content_type', 'cache_expires_at'
    ]
    search_fields = ['user__username', 'content_type__model']
    readonly_fields = [
        'user', 'content_type', 'object_id', 'action', 'field_name',
        'has_permission', 'cache_expires_at', 'created_at', 'updated_at'
    ]
    
    def content_type_display(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"
    content_type_display.short_description = 'Content Type'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')
    
    actions = ['clear_expired_cache']
    
    def clear_expired_cache(self, request, queryset):
        from django.utils import timezone
        expired_count = UserPermissionCache.objects.filter(
            cache_expires_at__lt=timezone.now()
        ).delete()[0]
        self.message_user(request, f"Cleared {expired_count} expired cache entries.")
    clear_expired_cache.short_description = "Clear expired cache entries"
