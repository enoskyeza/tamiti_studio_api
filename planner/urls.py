from django.urls import path, include
from rest_framework.routers import DefaultRouter

from planner.views import (
    schedule_preview, schedule_commit, replan, bulk_reschedule, productivity_dashboard,
    BlockListView, BlockDetailView,
    CalendarEventListCreateView, CalendarEventDetailView,
    DailyReviewViewSet, WorkGoalViewSet, ProductivityInsightViewSet
)

# Create router for viewsets
router = DefaultRouter()
router.register(r'daily-reviews', DailyReviewViewSet, basename='dailyreview')
router.register(r'work-goals', WorkGoalViewSet, basename='workgoal')
router.register(r'insights', ProductivityInsightViewSet, basename='productivityinsight')

urlpatterns = [
    # Schedule management
    path('schedule/preview/', schedule_preview, name='schedule-preview'),
    path('schedule/commit/', schedule_commit, name='schedule-commit'),
    path('replan/', replan, name='replan'),
    path('bulk-reschedule/', bulk_reschedule, name='bulk-reschedule'),
    
    # Time blocks and events
    path('blocks/', BlockListView.as_view(), name='block-list'),
    path('blocks/<int:pk>/', BlockDetailView.as_view(), name='block-detail'),
    path('events/', CalendarEventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', CalendarEventDetailView.as_view(), name='event-detail'),
    
    # Productivity dashboard
    path('dashboard/', productivity_dashboard, name='productivity-dashboard'),
    
    # Include router URLs
    path('', include(router.urls)),
]

