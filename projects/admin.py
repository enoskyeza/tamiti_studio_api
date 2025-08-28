from django.contrib import admin
from .models import Project, ProjectMember, Milestone, ProjectComment


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'client_name', 'status', 'priority',
        'completion_percentage', 'created_by', 'start_date', 'due_date'
    ]
    list_filter = ['status', 'priority', 'start_date', 'due_date']
    search_fields = ['name', 'client_name', 'description', 'created_by__email']
    readonly_fields = ['uuid', 'completion_percentage']
    autocomplete_fields = ['created_by']
    ordering = ['-created_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'client_name', 'description', 'status', 'priority')
        }),
        ('Timeline', {
            'fields': ('start_date', 'due_date')
        }),
        ('Budget & Time', {
            'fields': ('estimated_hours', 'actual_hours', 'budget', 'tags')
        }),
        ('Metadata', {
            'fields': ('created_by', 'completion_percentage')
        }),
    )


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ['project', 'user', 'role']
    search_fields = ['project__name', 'user__email']
    autocomplete_fields = ['project', 'user']


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'due_date', 'completed', 'reward', 'achievement_date']
    list_filter = ['completed']
    search_fields = ['project__name', 'name', 'reward']
    autocomplete_fields = ['project']
    readonly_fields = ['achievement_date']


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ['project', 'user', 'short_content', 'is_internal', 'created_at']
    list_filter = ['is_internal', 'created_at']
    search_fields = ['project__name', 'user__email', 'content']

    def short_content(self, obj):
        return (obj.content[:50] + '...') if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'
