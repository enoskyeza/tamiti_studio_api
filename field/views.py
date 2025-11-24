from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from core.api import AppContextLoggingPermission
from field.models import Zone, Lead, Visit, LeadAction
from field.serializers import (
    ZoneSerializer,
    LeadSerializer,
    LeadReadSerializer,
    VisitSerializer,
    VisitReadSerializer,
    LeadActionSerializer,
    LeadActionReadSerializer,
)


class StudioScopedMixin:
    context = "studio"


class ZoneViewSet(StudioScopedMixin, viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'region']


class LeadViewSet(StudioScopedMixin, viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('assigned_rep', 'zone').prefetch_related('actions').all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['business_name', 'contact_name', 'contact_phone']
    ordering_fields = ['lead_score', 'priority', 'follow_up_date']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return LeadReadSerializer
        return LeadSerializer

    @action(detail=False, methods=['get'])
    def hot(self, request):
        queryset = self.get_queryset().filter(priority__in=['high', 'critical'])
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class VisitViewSet(StudioScopedMixin, viewsets.ModelViewSet):
    queryset = Visit.objects.select_related('rep', 'zone', 'linked_lead').all()
    serializer_class = VisitSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['business_name', 'contact_name', 'contact_phone', 'location']
    ordering_fields = ['date_time']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return VisitReadSerializer
        return VisitSerializer

    @action(detail=True, methods=['post'])
    def convert_to_lead(self, request, pk=None):
        visit = self.get_object()
        lead = visit.convert_to_lead()
        return Response({"lead_id": lead.id if lead else None, "linked": bool(lead)})


class LeadActionViewSet(StudioScopedMixin, viewsets.ModelViewSet):
    queryset = LeadAction.objects.select_related('lead', 'created_by')
    serializer_class = LeadActionSerializer
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return LeadActionReadSerializer
        return LeadActionSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
