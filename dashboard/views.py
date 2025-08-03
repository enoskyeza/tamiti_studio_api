"""API endpoints for dashboard metrics."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    get_cached_dashboard_metrics,
    get_field_summary,
    get_finance_summary,
    get_leads_summary,
    get_project_summary,
    get_social_summary,
    get_task_summary,
)


class ProjectSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_project_summary(request.user))


class TaskSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_task_summary(request.user))


class FinanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_finance_summary(request.user))


class FieldSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_field_summary(request.user))


class LeadsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_leads_summary(request.user))


class SocialSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_social_summary(request.user))


class DashboardKPIView(APIView):
    """Return consolidated KPIs for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_cached_dashboard_metrics(request.user)
        return Response(data)

