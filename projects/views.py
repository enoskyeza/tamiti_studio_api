from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from rest_framework import generics, permissions
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from core.api import AppContextLoggingPermission
from projects.filters import ProjectFilter
from projects.models import Project, Milestone
from comments.models import Comment
from comments.serializers import CommentSerializer
from projects.serializers import (
    ProjectSerializer, ProjectSummarySerializer,
    MilestoneSerializer
)
from tasks.models import Task
from tasks.serializers import TaskSerializer
from tasks.filters import TaskFilter


class StudioScopedMixin:
    context = "studio"


class ProjectListCreateView(StudioScopedMixin, generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProjectFilter
    # Allow client ordering while keeping a stable default
    ordering_fields = ['id', 'name', 'created_at', 'updated_at', 'due_date', 'completion_percentage', 'priority', 'status']
    ordering = ['-updated_at', '-id']

    def get_serializer_class(self):
        return ProjectSummarySerializer if self.request.method == 'GET' else ProjectSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()
        user = self.request.user
        base_q = (
            Q(created_by=user) |
            Q(members__user=user) |
            Q(tasks__assigned_to=user) |
            Q(tasks__assigned_users=user)
        )
        qs = Project.objects.filter(base_q).distinct()
        if status := self.request.query_params.get('status'):
            qs = qs.filter(status=status)
        if priority := self.request.query_params.get('priority'):
            qs = qs.filter(priority=priority)
        if search := self.request.query_params.get('search'):
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        # Explicit deterministic ordering for stable pagination
        return qs.order_by('-updated_at', '-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProjectDetailView(StudioScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_q = (
            Q(created_by=user) |
            Q(members__user=user) |
            Q(tasks__assigned_to=user) |
            Q(tasks__assigned_users=user)
        )
        return Project.objects.filter(base_q).distinct()


class MilestoneListCreateView(StudioScopedMixin, generics.ListCreateAPIView):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['id', 'name', 'due_date', 'completed', 'created_at', 'updated_at']
    ordering = ['due_date', 'id']

    def get_queryset(self):
        user = self.request.user
        project_q = (
            Q(project__created_by=user) |
            Q(project__members__user=user) |
            Q(project__tasks__assigned_to=user) |
            Q(project__tasks__assigned_users=user)
        )
        qs = Milestone.objects.filter(project_q).distinct()
        return qs.order_by('due_date', 'id')


class MilestoneDetailView(StudioScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        project_q = (
            Q(project__created_by=user) |
            Q(project__members__user=user) |
            Q(project__tasks__assigned_to=user) |
            Q(project__tasks__assigned_users=user)
        )
        return Milestone.objects.filter(project_q).distinct()


class ProjectCommentListCreateView(StudioScopedMixin, generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]

    def get_queryset(self):
        user = self.request.user
        project_base_q = (
            Q(created_by=user) |
            Q(members__user=user) |
            Q(tasks__assigned_to=user) |
            Q(tasks__assigned_users=user)
        )
        project = Project.objects.filter(
            Q(id=self.kwargs['project_id']) & project_base_q
        ).first()
        if not project:
            return Comment.objects.none()
        # comments bound to this project via GFK
        return Comment.objects.filter(
            content_type__app_label='projects',
            content_type__model='project',
            object_id=project.id,
            is_deleted=False,
        ).select_related('author')

    def perform_create(self, serializer):
        user = self.request.user
        project_base_q = (
            Q(created_by=user) |
            Q(members__user=user) |
            Q(tasks__assigned_to=user) |
            Q(tasks__assigned_users=user)
        )
        project = Project.objects.get(
            Q(id=self.kwargs['project_id']) & project_base_q
        )
        serializer.save(
            author=self.request.user,
            content_type=ContentType.objects.get(app_label='projects', model='project'),
            object_id=project.id,
        )


class ProjectTaskListView(StudioScopedMixin, generics.ListAPIView):
    """List tasks for a given project with same filters as /tasks"""
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TaskFilter
    ordering_fields = [
        'id', 'title', 'created_at', 'updated_at', 'due_date',
        'status', 'priority', 'is_completed', 'kanban_position', 'position'
    ]
    ordering = ['is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id']

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.filter(project_id=self.kwargs['project_id']).filter(
            Q(created_by=user) |
            Q(assigned_to=user) |
            Q(assigned_users=user) |
            Q(project__created_by=user) |
            Q(project__members__user=user)
        ).distinct()
        return qs.order_by('is_completed', 'kanban_position', 'position', 'due_date', '-updated_at', '-id')
