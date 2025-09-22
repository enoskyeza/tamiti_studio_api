# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, Staff, UserPreferences, Tag

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'username', 'email', 'role', 'is_active', 'is_verified', 'is_temporary', 'expires_at', 'date_joined')
    list_filter = ('role', 'is_active', 'is_verified', 'is_staff', 'is_temporary', 'created_for_event')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = ('last_seen', 'streak_days', 'current_streak_started', 'total_tasks_completed', 'auto_generated_username')
    
    def get_list_display(self, request):
        """Show different columns for temporary vs regular users"""
        if request.GET.get('is_temporary__exact') == '1':
            return ('id', 'username', 'created_for_event', 'expires_at', 'is_active', 'date_joined')
        return self.list_display
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'phone', 'first_name', 'last_name', 'avatar', 'bio')}),
        ('Temporary User', {'fields': ('is_temporary', 'expires_at', 'created_for_event', 'auto_generated_username')}),
        ('Productivity', {'fields': ('streak_days', 'current_streak_started', 'total_tasks_completed', 'last_seen')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    actions = ['cleanup_expired_temporary_users']
    
    def cleanup_expired_temporary_users(self, request, queryset):
        """Admin action to clean up expired temporary users"""
        from django.utils import timezone
        expired_count = queryset.filter(
            is_temporary=True,
            expires_at__lt=timezone.now()
        ).delete()[0]
        self.message_user(request, f'Deleted {expired_count} expired temporary users.')
    cleanup_expired_temporary_users.short_description = "Delete expired temporary users"

# Proxy models don’t need registration unless you want custom views
admin.site.register(Customer)
admin.site.register(Staff)

@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'language', 'dark_mode', 'daily_summary')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('label', 'color')
    search_fields = ('label',)