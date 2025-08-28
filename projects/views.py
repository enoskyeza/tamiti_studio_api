from django.db.models import Q

from rest_framework import generics, permissions
from django_filters.rest_framework import DjangoFilterBackend

from projects.filters import ProjectFilter
from projects.models import Project, Milestone, ProjectComment
from projects.serializers import (
    ProjectSerializer, ProjectSummarySerializer,
    MilestoneSerializer, ProjectCommentSerializer
)


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
    serializer_class = ProjectCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProjectComment.objects.filter(
            project_id=self.kwargs['project_id'],
            project__created_by=self.request.user
        )

    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_id'], created_by=self.request.user)
        serializer.save(user=self.request.user, project=project)
