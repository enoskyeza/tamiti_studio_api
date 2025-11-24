from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Task, TaskGroup, KanbanBoard, KanbanColumn, BacklogItem, TaskChecklist
try:
    from planner.models import TimeBlock
except Exception:  # planner may not be migrated yet in some envs
    TimeBlock = None


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


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        'title', 'status', 'priority', linkify('project'), linkify('assigned_to'),
        'assigned_team', 'due_date', 'is_completed', 'completed_at'
    )
    class OverdueFilter(admin.SimpleListFilter):
        title = 'Overdue'
        parameter_name = 'overdue'

        def lookups(self, request, model_admin):
            return (
                ('1', 'Overdue'),
            )

        def queryset(self, request, queryset):
            if self.value() == '1':
                from django.utils import timezone
                return queryset.filter(is_completed=False, due_date__lt=timezone.now())
            return queryset

    class SnoozedFilter(admin.SimpleListFilter):
        title = 'Snoozed'
        parameter_name = 'snoozed'

        def lookups(self, request, model_admin):
            return (
                ('1', 'Snoozed'),
            )

        def queryset(self, request, queryset):
            if self.value() == '1':
                return queryset.exclude(snoozed_until__isnull=True)
            return queryset

    list_filter = (
        'status', 'priority', 'is_completed',
        ('project', admin.RelatedOnlyFieldListFilter),
        ('assigned_to', admin.RelatedOnlyFieldListFilter),
        ('assigned_users', admin.RelatedOnlyFieldListFilter),
        ('assigned_team', admin.RelatedOnlyFieldListFilter),
        'due_date', OverdueFilter, SnoozedFilter,
    )
    search_fields = [
        'title', 'description', 'assigned_to__email', 'project__name', 'tags__name'
    ]
    readonly_fields = ['uuid', 'completed_at', 'is_overdue', 'created_at', 'updated_at']
    autocomplete_fields = ['assigned_to', 'assigned_team', 'project', 'milestone', 'dependencies', 'parent']
    filter_horizontal = ('assigned_users',)
    ordering = ['is_completed', 'position', 'due_date']
    list_select_related = ('project', 'assigned_to', 'assigned_team')
    list_per_page = 50
    date_hierarchy = 'due_date'
    fieldsets = (
        (None, {
            'fields': ('project', 'title', 'description', 'status', 'priority', 'is_completed', 'origin_app')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_users', 'assigned_team', 'milestone', 'parent')
        }),
        ('Timing', {
            'fields': (
                'start_at', 'earliest_start_at', 'latest_finish_at', 'snoozed_until', 'backlog_date',
                'due_date', 'estimated_minutes', 'estimated_hours', 'actual_hours', 'is_hard_due', 'completed_at'
            )
        }),
        ('Meta', {
            'fields': ('tags', 'notes', 'context_energy', 'context_location', 'recurrence_rule', 'dependencies', 'created_by', 'position', 'uuid', 'created_at', 'updated_at')
        }),
    )

    actions = ['mark_completed', 'snooze_one_day']

    @admin.action(description="Mark selected tasks as completed")
    def mark_completed(self, request, queryset):
        queryset.update(is_completed=True, status='done')

    @admin.action(description="Snooze selected tasks by 1 day")
    def snooze_one_day(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        queryset.update(snoozed_until=timezone.now() + timedelta(days=1))

    class TaskChecklistInline(admin.TabularInline):
        model = TaskChecklist
        extra = 1
        fields = ('title', 'is_completed', 'position')
        ordering = ('position', 'created_at')

    if TimeBlock is not None:
        class TimeBlockInline(admin.TabularInline):
            model = TimeBlock
            extra = 0
            fields = ('start', 'end', 'status', 'is_break', 'source')
            readonly_fields = ()
            fk_name = 'task'

        inlines = [TaskChecklistInline, TimeBlockInline]
    else:
        inlines = [TaskChecklistInline]


@admin.register(TaskGroup)
class TaskGroupAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = [linkify('project'), 'name', 'order']
    autocomplete_fields = ['project']
    search_fields = ['project__name', 'name']
    list_select_related = ('project',)
    ordering = ['project__name', 'order']


class KanbanColumnInline(admin.TabularInline):
    model = KanbanColumn
    extra = 0
    fields = ('name', 'status_mapping', 'order', 'color', 'wip_limit')
    ordering = ('order',)


@admin.register(KanbanBoard)
class KanbanBoardAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ['name', linkify('project'), 'created_at']
    list_filter = ['project', 'created_at']
    search_fields = ['name', 'project__name']
    autocomplete_fields = ['project']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ('project',)
    inlines = [KanbanColumnInline]


@admin.register(KanbanColumn)
class KanbanColumnAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ['name', linkify('board'), 'status_mapping', 'order', 'task_count', 'wip_limit', 'is_wip_exceeded']
    list_filter = ['board', 'status_mapping', 'board__project']
    search_fields = ['name', 'board__name', 'board__project__name']
    autocomplete_fields = ['board']
    readonly_fields = ['created_at', 'updated_at', 'task_count', 'is_wip_exceeded']
    ordering = ['board', 'order']
    list_select_related = ('board', 'board__project')


@admin.register(BacklogItem)
class BacklogItemAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ['title', 'source', 'created_by', 'is_converted', 'converted_task_link', 'created_at']
    list_filter = ['source', 'is_converted', 'created_at']
    search_fields = ['title', 'created_by__username', 'created_by__email']
    readonly_fields = ['converted_to_task', 'is_converted', 'created_at', 'updated_at']
    autocomplete_fields = ['created_by']
    ordering = ['-created_at']
    list_select_related = ('created_by', 'converted_to_task')
    
    def converted_task_link(self, obj):
        if obj.converted_to_task:
            url = reverse("admin:tasks_task_change", args=[obj.converted_to_task.pk])
            return format_html('<a href="{}">{}</a>', url, obj.converted_to_task.title)
        return '—'
    converted_task_link.short_description = 'Converted Task'
    converted_task_link.admin_order_field = 'converted_to_task'
    
    actions = ['convert_to_tasks']
    
    @admin.action(description="Convert selected backlog items to tasks")
    def convert_to_tasks(self, request, queryset):
        converted_count = 0
        for item in queryset.filter(is_converted=False):
            item.convert_to_task()
            converted_count += 1
        
        self.message_user(request, f"Successfully converted {converted_count} backlog items to tasks.")


@admin.register(TaskChecklist)
class TaskChecklistAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ['title', 'task_link', 'is_completed', 'completed_at', 'position', 'created_at']
    list_filter = ['is_completed', 'created_at', 'task__project']
    search_fields = ['title', 'task__title', 'task__project__name']
    readonly_fields = ['completed_at', 'created_at', 'updated_at']
    autocomplete_fields = ['task']
    ordering = ['task', 'position', 'created_at']
    list_select_related = ('task', 'task__project')
    
    def task_link(self, obj):
        url = reverse("admin:tasks_task_change", args=[obj.task.pk])
        return format_html('<a href="{}">{}</a>', url, obj.task.title)
    task_link.short_description = 'Task'
    task_link.admin_order_field = 'task'
    
    actions = ['mark_completed', 'mark_incomplete']
    
    @admin.action(description="Mark selected checklist items as completed")
    def mark_completed(self, request, queryset):
        for item in queryset.filter(is_completed=False):
            item.mark_completed()
        self.message_user(request, f"Marked {queryset.count()} items as completed.")
    
    @admin.action(description="Mark selected checklist items as incomplete")
    def mark_incomplete(self, request, queryset):
        for item in queryset.filter(is_completed=True):
            item.mark_incomplete()
        self.message_user(request, f"Marked {queryset.count()} items as incomplete.")
