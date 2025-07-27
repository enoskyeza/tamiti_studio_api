from django.urls import path
from tasks.views import (
    TaskListCreateView, TaskDetailView, toggle_task_completion
)

urlpatterns = [
    path('', TaskListCreateView.as_view(), name='task-list-create'),
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
    path('<int:task_id>/toggle/', toggle_task_completion, name='toggle-task'),
]
