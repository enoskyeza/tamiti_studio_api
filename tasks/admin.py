from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Task, TaskGroup
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
        ('assigned_team', admin.RelatedOnlyFieldListFilter),
        'due_date', OverdueFilter, SnoozedFilter,
    )
    search_fields = [
        'title', 'description', 'assigned_to__email', 'project__name', 'tags__name'
    ]
    readonly_fields = ['uuid', 'completed_at', 'is_overdue', 'created_at', 'updated_at']
    autocomplete_fields = ['assigned_to', 'assigned_team', 'project', 'milestone', 'dependencies', 'parent']
    ordering = ['is_completed', 'position', 'due_date']
    list_select_related = ('project', 'assigned_to', 'assigned_team')
    list_per_page = 50
    date_hierarchy = 'due_date'
    fieldsets = (
        (None, {
            'fields': ('project', 'title', 'description', 'status', 'priority', 'is_completed', 'origin_app')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_team', 'milestone', 'parent')
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

    if TimeBlock is not None:
        class TimeBlockInline(admin.TabularInline):
            model = TimeBlock
            extra = 0
            fields = ('start', 'end', 'status', 'is_break', 'source')
            readonly_fields = ()
            fk_name = 'task'

        inlines = [TimeBlockInline]


@admin.register(TaskGroup)
class TaskGroupAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = [linkify('project'), 'name', 'order']
    autocomplete_fields = ['project']
    search_fields = ['project__name', 'name']
    list_select_related = ('project',)
    ordering = ['project__name', 'order']
