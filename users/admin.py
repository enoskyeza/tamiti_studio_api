# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Customer, Staff, UserPreferences, Tag

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'username', 'email', 'role', 'is_active', 'is_verified', 'date_joined', 'streak_days', 'total_tasks_completed', 'current_streak_started')
    list_filter = ('role', 'is_active', 'is_verified', 'is_staff')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = ('last_seen', 'streak_days', 'current_streak_started', 'total_tasks_completed')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'phone', 'first_name', 'last_name', 'avatar', 'bio')}),
        ('Productivity', {'fields': ('streak_days', 'current_streak_started', 'total_tasks_completed', 'last_seen')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

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