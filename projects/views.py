from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from rest_framework import generics, permissions
from django_filters.rest_framework import DjangoFilterBackend

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


class ProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProjectFilter

    def get_serializer_class(self):
        return ProjectSummarySerializer if self.request.method == 'GET' else ProjectSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()
        qs = Project.objects.filter(created_by=self.request.user)
        if status := self.request.query_params.get('status'):
            qs = qs.filter(status=status)
        if priority := self.request.query_params.get('priority'):
            qs = qs.filter(priority=priority)
        if search := self.request.query_params.get('search'):
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(created_by=self.request.user)


class MilestoneListCreateView(generics.ListCreateAPIView):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Milestone.objects.filter(project__created_by=self.request.user)


class MilestoneDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Milestone.objects.filter(project__created_by=self.request.user)


class ProjectCommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = Project.objects.filter(
            id=self.kwargs['project_id'], created_by=self.request.user
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
        project = Project.objects.get(id=self.kwargs['project_id'], created_by=self.request.user)
        serializer.save(
            author=self.request.user,
            content_type=ContentType.objects.get(app_label='projects', model='project'),
            object_id=project.id,
        )


class ProjectTaskListView(generics.ListAPIView):
    """List tasks for a given project with same filters as /tasks"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaskFilter

    def get_queryset(self):
        return Task.objects.filter(project_id=self.kwargs['project_id'], project__created_by=self.request.user)
