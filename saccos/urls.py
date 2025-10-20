from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SaccoOrganizationViewSet,
    SaccoMemberViewSet,
    MemberPassbookViewSet,
    PassbookSectionViewSet,
    PassbookEntryViewSet,
    DeductionRuleViewSet,
    CashRoundScheduleViewSet,
    WeeklyMeetingViewSet,
    WeeklyContributionViewSet,
    SaccoLoanViewSet,
    LoanPaymentViewSet,
    LoanGuarantorViewSet,
    SaccoEmergencySupportViewSet,
)
from .views_phase5 import (
    get_member_statement, get_loan_portfolio_report, get_financial_statement,
    get_attendance_report, get_savings_report, get_cash_round_report,
    get_member_ranking_report, get_dashboard_metrics, get_trend_analysis,
    get_member_growth_analysis, get_loan_performance_metrics,
    get_savings_growth_analysis, get_meeting_efficiency_metrics,
    setup_finance_accounts, get_financial_summary
)
from .views_phase6 import (
    SubscriptionPlanViewSet, SaccoSubscriptionViewSet,
    SubscriptionInvoiceViewSet, UsageMetricsViewSet
)
from .views_account import SaccoAccountViewSet

# Main router for all resources
router = DefaultRouter()

# Global resources
router.register(r'passbooks', MemberPassbookViewSet, basename='passbook')
router.register(r'sections', PassbookSectionViewSet, basename='passbook-section')
router.register(r'entries', PassbookEntryViewSet, basename='passbook-entry')
router.register(r'deduction-rules', DeductionRuleViewSet, basename='deduction-rule')
router.register(r'account', SaccoAccountViewSet, basename='sacco-account')

# Phase 3: Weekly Meetings
router.register(r'cash-round-schedules', CashRoundScheduleViewSet, basename='cash-round-schedule')
router.register(r'meetings', WeeklyMeetingViewSet, basename='weekly-meeting')
router.register(r'contributions', WeeklyContributionViewSet, basename='weekly-contribution')

# Phase 4: Loan Management
router.register(r'loans', SaccoLoanViewSet, basename='sacco-loan')
router.register(r'loan-payments', LoanPaymentViewSet, basename='loan-payment')
router.register(r'loan-guarantors', LoanGuarantorViewSet, basename='loan-guarantor')
router.register(r'emergency-support', SaccoEmergencySupportViewSet, basename='emergency-support')

# Phase 6: SaaS Features
router.register(r'subscription-plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscriptions', SaccoSubscriptionViewSet, basename='sacco-subscription')
router.register(r'invoices', SubscriptionInvoiceViewSet, basename='subscription-invoice')
router.register(r'usage-metrics', UsageMetricsViewSet, basename='usage-metrics')

# Phase 1 & 2 - Main SACCO endpoint (no 'organizations' prefix for frontend compatibility)
router.register(r'', SaccoOrganizationViewSet, basename='sacco')

urlpatterns = [
    path('', include(router.urls)),
    
    # Nested member routes under SACCO
    path('<int:sacco_pk>/members/', SaccoMemberViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sacco-member-list'),
    path('<int:sacco_pk>/members/me/', SaccoMemberViewSet.as_view({
        'get': 'me'
    }), name='sacco-member-me'),
    path('<int:sacco_pk>/members/<int:pk>/', SaccoMemberViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sacco-member-detail'),
    
    # Phase 3: Weekly meetings nested under SACCO
    path('<int:sacco_pk>/cash-round-schedules/', CashRoundScheduleViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sacco-cash-round-schedule-list'),
    path('<int:sacco_pk>/cash-round-schedules/<int:pk>/', CashRoundScheduleViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sacco-cash-round-schedule-detail'),
    path('<int:sacco_pk>/meetings/', WeeklyMeetingViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sacco-weekly-meeting-list'),
    path('<int:sacco_pk>/meetings/<int:pk>/', WeeklyMeetingViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sacco-weekly-meeting-detail'),
    
    # Phase 5: Reporting & Analytics
    path('<int:sacco_id>/reports/member-statement/<int:member_id>/', get_member_statement, name='member-statement'),
    path('<int:sacco_id>/reports/loan-portfolio/', get_loan_portfolio_report, name='loan-portfolio-report'),
    path('<int:sacco_id>/reports/financial-statement/', get_financial_statement, name='financial-statement'),
    path('<int:sacco_id>/reports/attendance/', get_attendance_report, name='attendance-report'),
    path('<int:sacco_id>/reports/savings/', get_savings_report, name='savings-report'),
    path('<int:sacco_id>/reports/cash-rounds/', get_cash_round_report, name='cash-round-report'),
    path('<int:sacco_id>/reports/member-rankings/', get_member_ranking_report, name='member-rankings'),
    
    # Phase 5: Analytics
    path('<int:sacco_id>/analytics/dashboard/', get_dashboard_metrics, name='dashboard-metrics'),
    path('<int:sacco_id>/analytics/trends/', get_trend_analysis, name='trend-analysis'),
    path('<int:sacco_id>/analytics/member-growth/', get_member_growth_analysis, name='member-growth'),
    path('<int:sacco_id>/analytics/loan-performance/', get_loan_performance_metrics, name='loan-performance'),
    path('<int:sacco_id>/analytics/savings-growth/', get_savings_growth_analysis, name='savings-growth'),
    path('<int:sacco_id>/analytics/meeting-efficiency/', get_meeting_efficiency_metrics, name='meeting-efficiency'),
    
    # Phase 5: Finance Integration
    path('<int:sacco_id>/finance/setup-accounts/', setup_finance_accounts, name='setup-finance-accounts'),
    path('<int:sacco_id>/finance/summary/', get_financial_summary, name='financial-summary'),
]
