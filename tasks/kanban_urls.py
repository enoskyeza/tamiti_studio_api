from django.urls import path
from tasks.kanban_views import (
    KanbanBoardListCreateView, KanbanBoardDetailView, ProjectKanbanBoardView,
    KanbanColumnListCreateView, KanbanColumnDetailView,
    move_task_to_column, reorder_task_in_column, initialize_project_kanban
)

urlpatterns = [
    # Kanban Board endpoints
    path('kanban/boards/', KanbanBoardListCreateView.as_view(), name='kanban-board-list-create'),
    path('kanban/boards/<int:pk>/', KanbanBoardDetailView.as_view(), name='kanban-board-detail'),
    path('kanban/projects/<int:project_id>/board/', ProjectKanbanBoardView.as_view(), name='project-kanban-board'),
    path('kanban/projects/<int:project_id>/initialize/', initialize_project_kanban, name='initialize-project-kanban'),
    
    # Kanban Column endpoints
    path('kanban/boards/<int:board_id>/columns/', KanbanColumnListCreateView.as_view(), name='kanban-column-list-create'),
    path('kanban/columns/<int:pk>/', KanbanColumnDetailView.as_view(), name='kanban-column-detail'),
    
    # Task movement endpoints
    path('kanban/tasks/<int:task_id>/move/', move_task_to_column, name='move-task-to-column'),
    path('kanban/tasks/<int:task_id>/reorder/', reorder_task_in_column, name='reorder-task-in-column'),
]
