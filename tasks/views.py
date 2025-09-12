from drf_spectacular.utils import extend_schema, OpenApiParameter

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Q

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from accounts.models import Department
from users.models import User
from common.enums import TaskStatus
from tasks.filters import TaskFilter
from tasks.models import Task, BacklogItem, TaskChecklist
from tasks.serializers import (
    TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer,
    TaskGroupSerializer, TaskToggleSerializer, BacklogItemSerializer,
    BacklogToTaskSerializer, TaskChecklistSerializer, TaskDetailSerializer
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
        if self.request.method in ['PUT', 'PATCH']:
            return TaskUpdateSerializer
        else:
            return TaskDetailSerializer

    def get_queryset(self):
        user = self.request.user
        team_q = Q()
        try:
            dept = getattr(user, 'staff_profile', None) and user.staff_profile.department
            if dept:
                team_q = Q(assigned_team=dept)
        except Exception:
            team_q = Q()
        return Task.objects.select_related('project', 'assigned_to', 'assigned_team').prefetch_related('checklist_items').filter(
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
        return Response({'message': 'until is required'}, status=status.HTTP_200_OK)

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
        return Response(serializer.data, status=status.HTTP_200_OK)


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


class BacklogItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing backlog items"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BacklogItemSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['source', 'is_converted']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return backlog items created by the current user"""
        return BacklogItem.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        """Set the created_by field to the current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def convert_to_task(self, request, pk=None):
        """Convert a backlog item to a task"""
        backlog_item = self.get_object()
        
        if backlog_item.is_converted:
            return Response(
                {'error': 'This backlog item has already been converted to a task.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the BacklogToTaskSerializer for validation and conversion
        serializer = BacklogToTaskSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            task = backlog_item.convert_to_task(**serializer.validated_data)
            
            return Response({
                'task': TaskSerializer(task).data,
                'backlog_item': BacklogItemSerializer(backlog_item).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskChecklistViewSet(viewsets.ModelViewSet):
    """ViewSet for managing task checklist items"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskChecklistSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ['position', 'created_at']
    ordering = ['position', 'created_at']

    def get_queryset(self):
        """Return checklist items for tasks accessible to the current user"""
        task_pk = self.kwargs.get('task_pk')
        if task_pk:
            # Filter by specific task if task_pk is provided (nested routing)
            user_tasks = Task.objects.filter(
                Q(created_by=self.request.user) | 
                Q(assigned_to=self.request.user) | 
                Q(project__created_by=self.request.user)
            ).values_list('id', flat=True)
            
            if int(task_pk) in user_tasks:
                return TaskChecklist.objects.filter(task_id=task_pk)
            else:
                return TaskChecklist.objects.none()
        else:
            # Return all checklist items for accessible tasks
            user_tasks = Task.objects.filter(
                Q(created_by=self.request.user) | 
                Q(assigned_to=self.request.user) | 
                Q(project__created_by=self.request.user)
            )
            return TaskChecklist.objects.filter(task__in=user_tasks)

    def perform_create(self, serializer):
        """Set the task field when creating a checklist item"""
        task_pk = self.kwargs.get('task_pk')
        if task_pk:
            # Verify user has access to the task
            try:
                task = Task.objects.get(
                    Q(id=task_pk),
                    Q(created_by=self.request.user) | 
                    Q(assigned_to=self.request.user) | 
                    Q(project__created_by=self.request.user)
                )
                serializer.save(task=task)
            except Task.DoesNotExist:
                raise permissions.PermissionDenied("You don't have access to this task.")
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def toggle_completion(self, request, pk=None, task_pk=None):
        """Toggle the completion status of a checklist item"""
        checklist_item = self.get_object()
        
        if checklist_item.is_completed:
            checklist_item.mark_incomplete()
            message = f'Checklist item "{checklist_item.title}" marked as incomplete.'
        else:
            checklist_item.mark_completed()
            message = f'Checklist item "{checklist_item.title}" marked as completed.'
        
        return Response({
            'message': message,
            'checklist_item': TaskChecklistSerializer(checklist_item).data
        })
