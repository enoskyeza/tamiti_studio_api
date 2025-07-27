import django_filters
from tasks.models import Task

class TaskFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr='iexact')
    priority = django_filters.CharFilter(lookup_expr='iexact')
    due_date = django_filters.DateFromToRangeFilter()

    class Meta:
        model = Task
        fields = ['project', 'status', 'priority', 'due_date']
