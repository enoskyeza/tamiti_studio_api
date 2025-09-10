from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from tasks.models import Task, KanbanBoard, KanbanColumn
from projects.models import Project
from tasks.serializers import (
    KanbanBoardSerializer, KanbanColumnSerializer, TaskMoveSerializer, 
    TaskReorderSerializer, TaskSerializer
)
from common.enums import TaskStatus


class KanbanBoardListCreateView(generics.ListCreateAPIView):
    """List and create Kanban boards"""
    serializer_class = KanbanBoardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KanbanBoard.objects.filter(project__created_by=self.request.user)

    def perform_create(self, serializer):
        project_id = self.request.data.get('project')
        project = get_object_or_404(Project, id=project_id, created_by=self.request.user)
        board = serializer.save(project=project)
        
        # Create default columns
        self.create_default_columns(board)

    def create_default_columns(self, board):
        """Create default Kanban columns for a new board"""
        default_columns = [
            {'name': 'To Do', 'status_mapping': TaskStatus.TODO, 'order': 0, 'color': '#EF4444'},
            {'name': 'In Progress', 'status_mapping': TaskStatus.IN_PROGRESS, 'order': 1, 'color': '#F59E0B'},
            {'name': 'Review', 'status_mapping': TaskStatus.REVIEW, 'order': 2, 'color': '#8B5CF6'},
            {'name': 'Done', 'status_mapping': TaskStatus.DONE, 'order': 3, 'color': '#10B981'},
        ]
        
        for col_data in default_columns:
            KanbanColumn.objects.create(board=board, **col_data)


class KanbanBoardDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a Kanban board"""
    serializer_class = KanbanBoardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KanbanBoard.objects.filter(project__created_by=self.request.user)


class ProjectKanbanBoardView(generics.RetrieveAPIView):
    """Get Kanban board for a specific project"""
    serializer_class = KanbanBoardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, id=project_id, created_by=self.request.user)
        
        # Get or create Kanban board for the project
        board, created = KanbanBoard.objects.get_or_create(
            project=project,
            defaults={'name': f'{project.name} Board'}
        )
        
        if created:
            # Create default columns for new board
            KanbanBoardListCreateView().create_default_columns(board)
        
        return board


class KanbanColumnListCreateView(generics.ListCreateAPIView):
    """List and create Kanban columns"""
    serializer_class = KanbanColumnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        board_id = self.kwargs.get('board_id')
        return KanbanColumn.objects.filter(
            board_id=board_id,
            board__project__created_by=self.request.user
        )

    def perform_create(self, serializer):
        board_id = self.kwargs['board_id']
        board = get_object_or_404(
            KanbanBoard, 
            id=board_id, 
            project__created_by=self.request.user
        )
        serializer.save(board=board)


class KanbanColumnDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a Kanban column"""
    serializer_class = KanbanColumnSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KanbanColumn.objects.filter(board__project__created_by=self.request.user)


@extend_schema(
    parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)],
    request=TaskMoveSerializer,
    responses=TaskSerializer,
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def move_task_to_column(request, task_id):
    """Move a task to a different Kanban column"""
    try:
        task = Task.objects.get(
            Q(id=task_id),
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user)
        )
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TaskMoveSerializer(data=request.data)
    if serializer.is_valid():
        target_column_id = serializer.validated_data['target_column_id']
        position = serializer.validated_data.get('position')
        
        try:
            target_column = KanbanColumn.objects.get(
                id=target_column_id,
                board__project__created_by=request.user
            )
        except KanbanColumn.DoesNotExist:
            return Response({'error': 'Column not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Move the task
        task.move_to_column(target_column, position)
        
        return Response(TaskSerializer(task).data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)],
    request=TaskReorderSerializer,
    responses=TaskSerializer,
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reorder_task_in_column(request, task_id):
    """Reorder a task within its current column"""
    try:
        task = Task.objects.get(
            Q(id=task_id),
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user)
        )
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TaskReorderSerializer(data=request.data)
    if serializer.is_valid():
        new_position = serializer.validated_data['new_position']
        
        # Reorder the task
        task.reorder_in_column(new_position)
        
        return Response(TaskSerializer(task).data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    parameters=[OpenApiParameter(name="project_id", type=int, location=OpenApiParameter.PATH)],
    responses=KanbanBoardSerializer,
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initialize_project_kanban(request, project_id):
    """Initialize Kanban board for a project with existing tasks"""
    try:
        project = Project.objects.get(id=project_id, created_by=request.user)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get or create Kanban board
    board, created = KanbanBoard.objects.get_or_create(
        project=project,
        defaults={'name': f'{project.name} Board'}
    )
    
    if created:
        # Create default columns
        KanbanBoardListCreateView().create_default_columns(board)
    
    # Assign existing tasks to appropriate columns based on their status
    columns = {col.status_mapping: col for col in board.columns.all() if col.status_mapping}
    
    for task in project.tasks.filter(kanban_column__isnull=True):
        if task.status in columns:
            column = columns[task.status]
            task.move_to_column(column)
    
    return Response(KanbanBoardSerializer(board).data)
