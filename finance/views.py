from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from django.db import models as dj_models
from django.utils import timezone
from finance.models import *
from finance.serializers import *


class BaseModelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = '__all__'
    search_fields = '__all__'

    def get_filterset_class(self):
        model = self.get_queryset().model

        class AutoFilterSet(df_filters.FilterSet):
            class Meta:
                model = model
                fields = '__all__'
                filter_overrides = {
                    dj_models.FileField: {
                        'filter_class': df_filters.CharFilter,
                    }
                }

        return AutoFilterSet


class PartyViewSet(BaseModelViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer


class AccountViewSet(BaseModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer


class InvoiceViewSet(BaseModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer

    @action(detail=False, methods=['get'])
    def unpaid(self, request):
        unpaid = self.queryset.filter(is_paid=False)
        serializer = self.get_serializer(unpaid, many=True)
        return Response(serializer.data)


class RequisitionViewSet(BaseModelViewSet):
    queryset = Requisition.objects.all()
    serializer_class = RequisitionSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending = self.queryset.filter(status='pending')
        return Response(self.get_serializer(pending, many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        requisition = self.get_object()
        requisition.approve(request.user)
        return Response(self.get_serializer(requisition).data)


class GoalViewSet(BaseModelViewSet):
    queryset = Goal.objects.prefetch_related('milestones')
    serializer_class = GoalSerializer

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        goal = self.get_object()
        return Response({
            "current": goal.current_amount,
            "target": goal.target_amount,
            "percentage": round((goal.current_amount / goal.target_amount) * 100, 2) if goal.target_amount else 0,
        })


class TransactionViewSet(BaseModelViewSet):
    queryset = Transaction.objects.select_related('account')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('-date')


class PaymentViewSet(BaseModelViewSet):
    queryset = Payment.objects.select_related('invoice', 'account', 'transaction')
    serializer_class = PaymentSerializer

    def perform_create(self, serializer):
        payment = serializer.save()
        # additional logic already handled in model save()

    @action(detail=False, methods=['get'])
    def by_goal(self, request):
        goal_id = request.query_params.get('goal')
        if goal_id:
            payments = self.queryset.filter(goal_id=goal_id)
            return Response(self.get_serializer(payments, many=True).data)
        return Response({"detail": "Missing goal param"}, status=status.HTTP_400_BAD_REQUEST)
