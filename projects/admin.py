from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.urls import reverse
from django.utils.html import format_html
from .models import Project, ProjectMember, Milestone
from comments.models import Comment
from tasks.models import Task


def linkify(field_name):
    def _linkify(obj):
        rel_obj = getattr(obj, field_name)
        if rel_obj is None:
            return '—'
        app_label = rel_obj._meta.app_label
        model_name = rel_obj._meta.model_name
        url = reverse(f"admin:{app_label}_{model_name}_change", args=[rel_obj.pk])
        return format_html('<a href="{}">{}</a>', url, str(rel_obj))

    _linkify.short_description = field_name.replace('_', ' ').title()
    _linkify.admin_order_field = field_name
    return _linkify


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    autocomplete_fields = ['project']
    readonly_fields = ['achievement_date']


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    autocomplete_fields = ['user']


class ProjectCommentInline(GenericTabularInline):
    model = Comment
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    extra = 0
    fields = ('author', 'content', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['author']


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ('title', 'status', 'assigned_to', 'due_date', 'is_completed')
    autocomplete_fields = ('assigned_to',)
    show_change_link = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        'name', 'client_name', 'status', 'priority', 'completion_percentage', linkify('created_by'),
        'start_date', 'due_date', 'is_overdue'
    )
    list_filter = (
        'status', 'priority', 'start_date', 'due_date',
    )
    search_fields = ['name', 'client_name', 'description', 'created_by__email']
    readonly_fields = ['uuid', 'completion_percentage', 'created_at', 'updated_at']
    autocomplete_fields = ['created_by']
    ordering = ['-created_at']
    list_select_related = ('created_by',)
    list_per_page = 50
    date_hierarchy = 'start_date'
    inlines = [TaskInline, MilestoneInline, ProjectMemberInline, ProjectCommentInline]
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
            'fields': ('created_by', 'completion_percentage', 'uuid', 'created_at', 'updated_at')
        }),
    )


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = [linkify('project'), linkify('user'), 'role']
    search_fields = ['project__name', 'user__email']
    autocomplete_fields = ['project', 'user']
    list_select_related = ('project', 'user')


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = [linkify('project'), 'name', 'due_date', 'completed', 'reward', 'achievement_date']
    list_filter = ['completed']
    search_fields = ['project__name', 'name', 'reward']
    autocomplete_fields = ['project']
    readonly_fields = ['achievement_date']
    list_select_related = ('project',)


## Removed per-domain ProjectComment admin in favor of global comments
