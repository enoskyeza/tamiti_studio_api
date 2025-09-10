from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from planner.models import BreakPolicy, AvailabilityTemplate, CalendarEvent, TimeBlock


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


@admin.register(BreakPolicy)
class BreakPolicyAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('owner_user', 'owner_team', 'focus_minutes', 'break_minutes', 'long_break_minutes', 'cycle_count', 'active')
    list_filter = ('active',)
    search_fields = ('owner_user__email', 'owner_team__name')
    autocomplete_fields = ('owner_user', 'owner_team')


@admin.register(AvailabilityTemplate)
class AvailabilityTemplateAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('day_of_week', 'start_time', 'end_time', 'owner_user', 'owner_team')
    list_filter = ('day_of_week',)
    search_fields = ('owner_user__email', 'owner_team__name')
    autocomplete_fields = ('owner_user', 'owner_team')


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('title', 'start', 'end', 'is_busy', 'source', 'owner_user', 'owner_team')
    list_filter = ('is_busy', 'source')
    search_fields = ('title', 'description', 'owner_user__email', 'owner_team__name')
    date_hierarchy = 'start'
    autocomplete_fields = ('owner_user', 'owner_team')


@admin.register(TimeBlock)
class TimeBlockAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ('title', 'start', 'end', 'status', 'is_break', linkify('task'), 'owner_user', 'owner_team')
    list_filter = ('status', 'is_break')
    search_fields = ('title', 'task__title', 'owner_user__email', 'owner_team__name')
    date_hierarchy = 'start'
    autocomplete_fields = ('task', 'owner_user', 'owner_team')
    list_select_related = ('task', 'owner_user', 'owner_team')
