"""API endpoints for dashboard metrics."""

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    DashboardKPISerializer,
    FieldSummarySerializer,
    FinanceSummarySerializer,
    LeadsSummarySerializer,
    ProjectSummarySerializer,
    SocialSummarySerializer,
    TaskSummarySerializer,
)
from .services import (
    get_cached_dashboard_metrics,
    get_field_summary,
    get_finance_summary,
    get_leads_summary,
    get_project_summary,
    get_social_summary,
    get_task_summary,
)


class ProjectSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectSummarySerializer

    @extend_schema(responses=ProjectSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_project_summary(request.user))
        return Response(serializer.data)


class TaskSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSummarySerializer

    @extend_schema(responses=TaskSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_task_summary(request.user))
        return Response(serializer.data)


class FinanceSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FinanceSummarySerializer

    @extend_schema(responses=FinanceSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_finance_summary(request.user))
        return Response(serializer.data)


class FieldSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FieldSummarySerializer

    @extend_schema(responses=FieldSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_field_summary(request.user))
        return Response(serializer.data)


class LeadsSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LeadsSummarySerializer

    @extend_schema(responses=LeadsSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_leads_summary(request.user))
        return Response(serializer.data)


class SocialSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SocialSummarySerializer

    @extend_schema(responses=SocialSummarySerializer)
    def get(self, request):
        serializer = self.get_serializer(get_social_summary(request.user))
        return Response(serializer.data)


class DashboardKPIView(generics.GenericAPIView):
    """Return consolidated KPIs for the authenticated user."""

    permission_classes = [IsAuthenticated]
    serializer_class = DashboardKPISerializer

    @extend_schema(responses=DashboardKPISerializer)
    def get(self, request):
        data = get_cached_dashboard_metrics(request.user)
        serializer = self.get_serializer(data)
        return Response(serializer.data)
