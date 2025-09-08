import django_filters
from django.db.models import Q
from tasks.models import Task

class TaskFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr='iexact')
    priority = django_filters.CharFilter(lookup_expr='iexact')
    due_date = django_filters.DateFromToRangeFilter()
    assigned_to = django_filters.NumberFilter(field_name='assigned_to__id')
    assigned_team = django_filters.NumberFilter(field_name='assigned_team__id')
    origin_app = django_filters.CharFilter(field_name='origin_app', lookup_expr='iexact')
    tag = django_filters.CharFilter(method='filter_tag')
    snoozed = django_filters.BooleanFilter(method='filter_snoozed')
    overdue = django_filters.BooleanFilter(method='filter_overdue')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = Task
        fields = [
            'project', 'status', 'priority', 'due_date', 'assigned_to', 'assigned_team', 'origin_app',
        ]

    def filter_tag(self, queryset, name, value):
        return queryset.filter(tags__name__in=[value])

    def filter_snoozed(self, queryset, name, value: bool):
        if value:
            return queryset.filter(snoozed_until__isnull=False)
        return queryset.filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lt=self._now()))

    def filter_overdue(self, queryset, name, value: bool):
        if not value:
            return queryset
        from django.utils import timezone
        return queryset.filter(is_completed=False, due_date__lt=timezone.now())

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(description__icontains=value))

    def _now(self):
        from django.utils import timezone
        return timezone.now()
