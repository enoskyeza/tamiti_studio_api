import django_filters
from projects.models import Project

class ProjectFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr='iexact')
    priority = django_filters.CharFilter(lookup_expr='iexact')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Project
        fields = ['status', 'priority', 'name']
