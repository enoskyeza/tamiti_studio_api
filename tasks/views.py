from drf_spectacular.utils import extend_schema, OpenApiParameter

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Q

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from accounts.models import Department
from users.models import User
from common.enums import TaskStatus
from tasks.filters import TaskFilter
from tasks.models import Task
from tasks.serializers import (
    TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer,
    TaskGroupSerializer, TaskToggleSerializer
)


class TaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TaskFilter
    # Allow client ordering with a stable default
    ordering_fields = [
        'id', 'title', 'created_at', 'updated_at', 'due_date',
        'status', 'priority', 'is_completed', 'kanban_position', 'position'
    ]
    # Keep default close to model Meta.ordering while adding tie-breakers
    ordering = ['is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id']

    def get_serializer_class(self):
        return TaskCreateSerializer if self.request.method == 'POST' else TaskSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        user: User = self.request.user
        # base access: tasks you own, tasks on your projects, tasks assigned to you, and your team tasks
        team_q = Q()
        try:
            dept: Department | None = getattr(user, 'staff_profile', None) and user.staff_profile.department
            if dept:
                team_q = Q(assigned_team=dept)
        except Exception:
            team_q = Q()
        qs = Task.objects.select_related('project', 'assigned_to', 'assigned_team').prefetch_related('tags').filter(
            Q(created_by=user) |
            Q(project__created_by=user) |
            Q(assigned_to=user) |
            team_q
        ).distinct()
        # optional shortcut: personal tasks only
        personal = self.request.query_params.get('personal')
        if personal in {'1', 'true', 'True'}:
            qs = qs.filter(project__isnull=True).filter(Q(assigned_to=user) | Q(created_by=user))
        # Explicit deterministic ordering for stable pagination
        return qs.order_by('is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return TaskUpdateSerializer if self.request.method in ['PUT', 'PATCH'] else TaskSerializer

    def get_queryset(self):
        user = self.request.user
        team_q = Q()
        try:
            dept = getattr(user, 'staff_profile', None) and user.staff_profile.department
            if dept:
                team_q = Q(assigned_team=dept)
        except Exception:
            team_q = Q()
        return Task.objects.select_related('project', 'assigned_to', 'assigned_team').filter(
            Q(created_by=user) | Q(assigned_to=user) | Q(project__created_by=user) | team_q
        ).distinct()


@extend_schema(
    parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)],
    request=None,
    responses=TaskToggleSerializer,  # or TaskSerializer if you prefer the full task structure
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_task_completion(request, task_id):
    try:
        task = Task.objects.get(
            Q(id=task_id),
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user)
        )
        task.is_completed = not task.is_completed
        task.save()
        return Response({
            'task': TaskSerializer(task).data,
            'message': f'Task {"completed" if task.is_completed else "reopened"}'
        })
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)])
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def complete_task(request, task_id):
    """Mark a task complete (sets is_completed, status, completed_at)."""
    try:
        task = Task.objects.get(
            Q(id=task_id),
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user)
        )
        task.is_completed = True
        task.status = TaskStatus.DONE
        task.save()
        return Response(TaskSerializer(task).data)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)])
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def snooze_task(request, task_id):
    """Snooze a task until a given datetime. Body: {"until": ISODateTime}"""
    until = request.data.get('until')
    if not until:
        return Response({'error': 'until is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(until)
        if not dt:
            return Response({'error': 'invalid datetime format'}, status=status.HTTP_400_BAD_REQUEST)
        task = Task.objects.get(
            Q(id=task_id),
            Q(created_by=request.user) | Q(assigned_to=request.user) | Q(project__created_by=request.user)
        )
        task.snoozed_until = dt
        task.save(update_fields=['snoozed_until', 'updated_at'])
        return Response(TaskSerializer(task).data)
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)


class TeamTaskListView(generics.ListAPIView):
    """List tasks for a given team/department ID with full filtering support."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TaskFilter
    serializer_class = TaskSerializer
    ordering_fields = [
        'id', 'title', 'created_at', 'updated_at', 'due_date',
        'status', 'priority', 'is_completed', 'kanban_position', 'position'
    ]
    ordering = ['is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id']

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        qs = Task.objects.filter(assigned_team_id=team_id)
        return qs.order_by('is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id')
