from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tasks.views import (
    TaskListCreateView, TaskDetailView, toggle_task_completion,
    complete_task, snooze_task, TeamTaskListView, BacklogItemViewSet,
    TaskChecklistViewSet
)

# Create routers for ViewSets
router = DefaultRouter()
router.register(r'backlog', BacklogItemViewSet, basename='backlog')
router.register(r'checklists', TaskChecklistViewSet, basename='checklist')

# Nested URLs for task checklists will be handled manually

urlpatterns = [
    path('', TaskListCreateView.as_view(), name='task-list-create'),
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
    path('<int:task_id>/toggle/', toggle_task_completion, name='toggle-task'),
    path('<int:task_id>/complete/', complete_task, name='complete-task'),
    path('<int:task_id>/snooze/', snooze_task, name='snooze-task'),
    path('teams/<int:team_id>/', TeamTaskListView.as_view(), name='team-task-list'),
    
    # Include router URLs
    path('', include(router.urls)),
    
    # Manual nested routes for task checklists
    path('<int:task_pk>/checklists/', TaskChecklistViewSet.as_view({'get': 'list', 'post': 'create'}), name='task-checklist-list'),
    path('<int:task_pk>/checklists/<int:pk>/', TaskChecklistViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='task-checklist-detail'),
    path('<int:task_pk>/checklists/<int:pk>/toggle/', TaskChecklistViewSet.as_view({'post': 'toggle_completion'}), name='task-checklist-toggle'),
    
    # Include Kanban URLs
    path('', include('tasks.kanban_urls')),
]
