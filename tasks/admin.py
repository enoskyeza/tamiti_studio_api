from django.contrib import admin
from .models import Task, TaskGroup


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'status', 'priority', 'assigned_to',
        'project', 'due_date', 'is_completed', 'completed_at'
    ]
    list_filter = ['status', 'priority', 'due_date', 'is_completed']
    search_fields = ['title', 'description', 'assigned_to__email', 'project__name']
    readonly_fields = ['uuid', 'completed_at', 'is_overdue']
    autocomplete_fields = ['assigned_to', 'project', 'milestone', 'dependencies']
    ordering = ['is_completed', 'position', 'due_date']
    fieldsets = (
        (None, {
            'fields': ('project', 'title', 'description', 'status', 'priority', 'is_completed')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'milestone', 'origin_app')
        }),
        ('Timing', {
            'fields': ('due_date', 'estimated_hours', 'actual_hours', 'completed_at')
        }),
        ('Meta', {
            'fields': ('tags', 'notes', 'dependencies', 'created_by', 'position')
        }),
    )


@admin.register(TaskGroup)
class TaskGroupAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'order']
    autocomplete_fields = ['project']
