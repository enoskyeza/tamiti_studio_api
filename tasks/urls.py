from django.urls import path, include
from tasks.views import (
    TaskListCreateView, TaskDetailView, toggle_task_completion,
    complete_task, snooze_task, TeamTaskListView
)

urlpatterns = [
    path('', TaskListCreateView.as_view(), name='task-list-create'),
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
    path('<int:task_id>/toggle/', toggle_task_completion, name='toggle-task'),
    path('<int:task_id>/complete/', complete_task, name='complete-task'),
    path('<int:task_id>/snooze/', snooze_task, name='snooze-task'),
    path('teams/<int:team_id>/', TeamTaskListView.as_view(), name='team-task-list'),
    
    # Include Kanban URLs
    path('', include('tasks.kanban_urls')),
]
