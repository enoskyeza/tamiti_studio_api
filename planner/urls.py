from django.urls import path

from planner.views import (
    schedule_preview, schedule_commit, replan,
    BlockListView, BlockDetailView,
    CalendarEventListCreateView, CalendarEventDetailView,
)

urlpatterns = [
    path('schedule/preview', schedule_preview, name='schedule-preview'),
    path('schedule/commit', schedule_commit, name='schedule-commit'),
    path('replan', replan, name='replan'),
    path('blocks', BlockListView.as_view(), name='block-list'),
    path('blocks/<int:pk>/', BlockDetailView.as_view(), name='block-detail'),
    path('events', CalendarEventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', CalendarEventDetailView.as_view(), name='event-detail'),
]

