from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from core.api import AppContextLoggingPermission
from .models import (
    SaccoOrganization, SubscriptionPlan, SaccoSubscription,
    SubscriptionInvoice, UsageMetrics
)
from .serializers import (
    SubscriptionPlanSerializer, SaccoSubscriptionSerializer,
    SubscriptionInvoiceSerializer, UsageMetricsSerializer
)
from .services.subscription_service import SubscriptionService


class SaccoScopedMixin:
    context = "sacco"
    permission_classes = [IsAuthenticated, AppContextLoggingPermission]


# ============================================================================
# PHASE 6: SAAS FEATURES VIEWS
# ============================================================================


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Subscription Plan management
    Phase 6: SaaS Features
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    
    def get_permissions(self):
        """Allow anyone to view public plans"""
        if self.action == 'list' or self.action == 'retrieve':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """Filter to public plans for unauthenticated users"""
        if self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        ):
            return SubscriptionPlan.objects.all()
        
        # Public users see only active, public plans
        return SubscriptionPlan.objects.filter(is_active=True, is_public=True)


class SaccoSubscriptionViewSet(SaccoScopedMixin, viewsets.ModelViewSet):
    """
    ViewSet for SACCO Subscription management
    Phase 6: SaaS Features
    """
    queryset = SaccoSubscription.objects.all()
    serializer_class = SaccoSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter subscriptions by SACCO or user access"""
        sacco_id = self.request.query_params.get('sacco')
        
        if sacco_id:
            return SaccoSubscription.objects.filter(sacco_id=sacco_id)
        
        # Admin users see all
        if self.request.user.is_staff or self.request.user.is_superuser:
            return SaccoSubscription.objects.all()
        
        # Regular users see only their SACCO's subscription
        if hasattr(self.request.user, 'sacco_membership'):
            return SaccoSubscription.objects.filter(
                sacco=self.request.user.sacco_membership.sacco
            )
        
        return SaccoSubscription.objects.none()
    
    @action(detail=False, methods=['post'])
    def create_trial(self, request):
        """Create a trial subscription"""
        sacco_id = request.data.get('sacco')
        plan_id = request.data.get('plan')
        trial_days = request.data.get('trial_days', 30)
        
        sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        subscription = SubscriptionService.create_trial_subscription(
            sacco=sacco,
            plan=plan,
            trial_days=trial_days
        )
        
        serializer = self.get_serializer(subscription)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a subscription after payment"""
        subscription = self.get_object()
        payment_method = request.data.get('payment_method', 'manual')
        reference = request.data.get('reference', '')
        
        result = SubscriptionService.activate_subscription(
            subscription=subscription,
            payment_method=payment_method,
            reference=reference
        )
        
        subscription_serializer = self.get_serializer(result['subscription'])
        invoice_serializer = SubscriptionInvoiceSerializer(result['invoice'])
        
        return Response({
            'subscription': subscription_serializer.data,
            'invoice': invoice_serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew a subscription"""
        subscription = self.get_object()
        payment_method = request.data.get('payment_method', 'auto')
        reference = request.data.get('reference', '')
        
        result = SubscriptionService.renew_subscription(
            subscription=subscription,
            payment_method=payment_method,
            reference=reference
        )
        
        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        subscription_serializer = self.get_serializer(result['subscription'])
        invoice_serializer = SubscriptionInvoiceSerializer(result['invoice'])
        
        return Response({
            'subscription': subscription_serializer.data,
            'invoice': invoice_serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def upgrade(self, request, pk=None):
        """Upgrade to a different plan"""
        subscription = self.get_object()
        new_plan_id = request.data.get('plan')
        
        new_plan = get_object_or_404(SubscriptionPlan, id=new_plan_id)
        
        updated = SubscriptionService.upgrade_subscription(
            subscription=subscription,
            new_plan=new_plan
        )
        
        serializer = self.get_serializer(updated)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend a subscription"""
        subscription = self.get_object()
        reason = request.data.get('reason', '')
        
        updated = SubscriptionService.suspend_subscription(
            subscription=subscription,
            reason=reason
        )
        
        serializer = self.get_serializer(updated)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a subscription"""
        subscription = self.get_object()
        immediate = request.data.get('immediate', False)
        
        updated = SubscriptionService.cancel_subscription(
            subscription=subscription,
            immediate=immediate
        )
        
        serializer = self.get_serializer(updated)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get comprehensive subscription status"""
        subscription = self.get_object()
        
        status_data = SubscriptionService.get_subscription_status(
            sacco=subscription.sacco
        )
        
        return Response(status_data)
    
    @action(detail=True, methods=['get'])
    def usage_limits(self, request, pk=None):
        """Check usage against subscription limits"""
        subscription = self.get_object()
        
        limits = SubscriptionService.check_usage_limits(
            sacco=subscription.sacco
        )
        
        return Response(limits)


class SubscriptionInvoiceViewSet(SaccoScopedMixin, viewsets.ModelViewSet):
    """
    ViewSet for Subscription Invoice management
    Phase 6: SaaS Features
    """
    queryset = SubscriptionInvoice.objects.all()
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter invoices by subscription or SACCO"""
        subscription_id = self.request.query_params.get('subscription')
        sacco_id = self.request.query_params.get('sacco')
        
        queryset = SubscriptionInvoice.objects.all()
        
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)
        elif sacco_id:
            queryset = queryset.filter(subscription__sacco_id=sacco_id)
        elif hasattr(self.request.user, 'sacco_membership'):
            queryset = queryset.filter(
                subscription__sacco=self.request.user.sacco_membership.sacco
            )
        else:
            return SubscriptionInvoice.objects.none()
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid"""
        invoice = self.get_object()
        
        from django.utils import timezone
        
        invoice.status = 'paid'
        invoice.paid_date = timezone.now().date()
        invoice.payment_method = request.data.get('payment_method', 'manual')
        invoice.payment_reference = request.data.get('reference', '')
        invoice.save()
        
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)


class UsageMetricsViewSet(SaccoScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Usage Metrics (read-only)
    Phase 6: SaaS Features
    """
    queryset = UsageMetrics.objects.all()
    serializer_class = UsageMetricsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter metrics by SACCO"""
        sacco_id = self.request.query_params.get('sacco')
        
        if sacco_id:
            return UsageMetrics.objects.filter(sacco_id=sacco_id)
        
        # Admin users see all
        if self.request.user.is_staff or self.request.user.is_superuser:
            return UsageMetrics.objects.all()
        
        # Regular users see only their SACCO's metrics
        if hasattr(self.request.user, 'sacco_membership'):
            return UsageMetrics.objects.filter(
                sacco=self.request.user.sacco_membership.sacco
            )
        
        return UsageMetrics.objects.none()
    
    @action(detail=False, methods=['post'])
    def record_current_period(self, request):
        """Record usage metrics for current period"""
        sacco_id = request.data.get('sacco')
        
        sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
        
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        period_start = today.replace(day=1)
        
        # Calculate period end (last day of month)
        next_month = period_start + timedelta(days=32)
        period_end = next_month.replace(day=1) - timedelta(days=1)
        
        metrics = SubscriptionService.record_usage_metrics(
            sacco=sacco,
            period_start=period_start,
            period_end=period_end
        )
        
        serializer = self.get_serializer(metrics)
        return Response(serializer.data)
