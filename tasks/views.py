from drf_spectacular.utils import extend_schema, OpenApiParameter

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from tasks.filters import TaskFilter
from tasks.models import Task
from tasks.serializers import (
    TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer,
    TaskGroupSerializer, TaskToggleSerializer
)


class TaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter

    def get_serializer_class(self):
        return TaskCreateSerializer if self.request.method == 'POST' else TaskSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        qs = Task.objects.filter(project__created_by=self.request.user)
        if pid := self.request.query_params.get('project'):
            qs = qs.filter(project_id=pid)
        if status_ := self.request.query_params.get('status'):
            qs = qs.filter(status=status_)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return TaskUpdateSerializer if self.request.method in ['PUT', 'PATCH'] else TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(project__created_by=self.request.user)


@extend_schema(
    parameters=[OpenApiParameter(name="task_id", type=int, location=OpenApiParameter.PATH)],
    request=None,
    responses=TaskToggleSerializer,  # or TaskSerializer if you prefer the full task structure
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_task_completion(request, task_id):
    try:
        task = Task.objects.get(id=task_id, project__created_by=request.user)
        task.is_completed = not task.is_completed
        task.save()
        return Response({
            'task': TaskSerializer(task).data,
            'message': f'Task {"completed" if task.is_completed else "reopened"}'
        })
    except Task.DoesNotExist:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
