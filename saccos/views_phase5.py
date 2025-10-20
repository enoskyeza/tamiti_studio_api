from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import SaccoOrganization, SaccoMember
from .services.reporting_service import ReportingService
from .services.analytics_service import AnalyticsService
from .services.finance_integration_service import FinanceIntegrationService


# ============================================================================
# PHASE 5: REPORTING & ANALYTICS VIEWS
# ============================================================================


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_member_statement(request, sacco_id, member_id):
    """
    Get comprehensive member statement
    
    Query params:
        - start_date: YYYY-MM-DD (optional)
        - end_date: YYYY-MM-DD (optional)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    member = get_object_or_404(SaccoMember, id=member_id, sacco=sacco)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Parse dates if provided
    if start_date:
        from django.utils.dateparse import parse_date
        start_date = parse_date(start_date)
    if end_date:
        from django.utils.dateparse import parse_date
        end_date = parse_date(end_date)
    
    statement = ReportingService.generate_member_statement(
        member=member,
        start_date=start_date,
        end_date=end_date
    )
    
    return Response(statement)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_loan_portfolio_report(request, sacco_id):
    """
    Get loan portfolio report
    
    Query params:
        - as_of_date: YYYY-MM-DD (optional)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    as_of_date = request.query_params.get('as_of_date')
    if as_of_date:
        from django.utils.dateparse import parse_date
        as_of_date = parse_date(as_of_date)
    
    report = ReportingService.generate_loan_portfolio_report(
        sacco=sacco,
        as_of_date=as_of_date
    )
    
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_financial_statement(request, sacco_id):
    """
    Get financial statement (Income & Expense)
    
    Query params:
        - start_date: YYYY-MM-DD (required)
        - end_date: YYYY-MM-DD (required)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    from django.utils.dateparse import parse_date
    start_date = parse_date(start_date)
    end_date = parse_date(end_date)
    
    statement = ReportingService.generate_financial_statement(
        sacco=sacco,
        start_date=start_date,
        end_date=end_date
    )
    
    return Response(statement)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_report(request, sacco_id):
    """
    Get attendance report
    
    Query params:
        - start_date: YYYY-MM-DD (required)
        - end_date: YYYY-MM-DD (required)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    from django.utils.dateparse import parse_date
    start_date = parse_date(start_date)
    end_date = parse_date(end_date)
    
    report = ReportingService.generate_attendance_report(
        sacco=sacco,
        start_date=start_date,
        end_date=end_date
    )
    
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_savings_report(request, sacco_id):
    """
    Get savings accumulation report
    
    Query params:
        - start_date: YYYY-MM-DD (optional)
        - end_date: YYYY-MM-DD (optional)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if start_date:
        from django.utils.dateparse import parse_date
        start_date = parse_date(start_date)
    if end_date:
        from django.utils.dateparse import parse_date
        end_date = parse_date(end_date)
    
    report = ReportingService.generate_savings_report(
        sacco=sacco,
        start_date=start_date,
        end_date=end_date
    )
    
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cash_round_report(request, sacco_id):
    """
    Get cash round completion report
    
    Query params:
        - year: YYYY (optional, defaults to current year)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    year = request.query_params.get('year')
    if year:
        year = int(year)
    
    report = ReportingService.generate_cash_round_report(
        sacco=sacco,
        year=year
    )
    
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_member_ranking_report(request, sacco_id):
    """
    Get member ranking by various metrics
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    report = ReportingService.generate_member_ranking_report(sacco=sacco)
    
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_metrics(request, sacco_id):
    """
    Get dashboard metrics for SACCO
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    metrics = AnalyticsService.get_dashboard_metrics(sacco=sacco)
    
    # Get account balance from SACCO account
    account_balance = Decimal('0')
    try:
        if hasattr(sacco, 'sacco_account') and sacco.sacco_account:
            account_balance = sacco.sacco_account.current_balance
        else:
            # Try to get or create the account
            sacco_account = sacco.get_or_create_account()
            if sacco_account and hasattr(sacco_account, 'account'):
                account_balance = sacco_account.account.balance
    except Exception as e:
        # Log but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not get SACCO account balance: {str(e)}")
    
    # Get actual member count
    total_members = SaccoMember.objects.filter(sacco=sacco).count()
    active_members = SaccoMember.objects.filter(sacco=sacco, status='active').count()
    
    # Get next meeting if exists
    from saccos.models import WeeklyMeeting
    next_meeting = WeeklyMeeting.objects.filter(
        sacco=sacco,
        meeting_date__gte=timezone.now().date(),
        status='planned'
    ).order_by('meeting_date').first()
    
    # Get current cash round recipient
    from saccos.models import CashRoundSchedule
    current_schedule = CashRoundSchedule.objects.filter(
        sacco=sacco,
        is_active=True,
        start_date__lte=timezone.now().date()
    ).order_by('-start_date').first()
    
    current_recipient = None
    if current_schedule:
        current_position = current_schedule.current_position or 0
        if current_position < len(current_schedule.rotation_order):
            member_id = current_schedule.rotation_order[current_position]
            try:
                current_recipient = SaccoMember.objects.get(id=member_id)
            except SaccoMember.DoesNotExist:
                pass
    
    flattened = {
        'total_members': total_members,
        'active_members': active_members,
        'total_savings': str(metrics['savings']['total']),
        'account_balance': str(account_balance),
        'total_loans': str(metrics['loans'].get('outstanding_amount', 0)),
        'outstanding_loans': str(metrics['loans'].get('outstanding_amount', 0)),
        'this_week_collection': str(metrics['meetings'].get('total_collected', 0)),
        'attendance_rate': 0,
        'next_meeting_date': next_meeting.meeting_date.isoformat() if next_meeting else None,
        'current_recipient': {
            'id': current_recipient.id,
            'member_number': current_recipient.member_number,
            'first_name': current_recipient.user.first_name,
            'last_name': current_recipient.user.last_name,
        } if current_recipient else None,
    }
    
    return Response(flattened)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trend_analysis(request, sacco_id):
    """
    Get trend analysis
    
    Query params:
        - months: Number of months (optional, default 6)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    months = int(request.query_params.get('months', 6))
    
    trends = AnalyticsService.get_trend_analysis(sacco=sacco, months=months)
    
    return Response(trends)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_member_growth_analysis(request, sacco_id):
    """
    Get member growth analysis
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    analysis = AnalyticsService.get_member_growth_analysis(sacco=sacco)
    
    return Response(analysis)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_loan_performance_metrics(request, sacco_id):
    """
    Get loan performance metrics
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    metrics = AnalyticsService.get_loan_performance_metrics(sacco=sacco)
    
    return Response(metrics)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_savings_growth_analysis(request, sacco_id):
    """
    Get savings growth analysis
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    analysis = AnalyticsService.get_savings_growth_analysis(sacco=sacco)
    
    return Response(analysis)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_meeting_efficiency_metrics(request, sacco_id):
    """
    Get meeting efficiency metrics
    
    Query params:
        - months: Number of months (optional, default 3)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    months = int(request.query_params.get('months', 3))
    
    metrics = AnalyticsService.get_meeting_efficiency_metrics(sacco=sacco, months=months)
    
    return Response(metrics)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_finance_accounts(request, sacco_id):
    """
    Set up finance accounts for a SACCO
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    accounts = FinanceIntegrationService.setup_sacco_accounts(sacco=sacco)
    
    return Response({
        'message': 'Finance accounts created successfully',
        'accounts': {
            'bank': accounts['bank'].id,
            'cash': accounts['cash'].id,
            'loans': accounts['loans'].id
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_financial_summary(request, sacco_id):
    """
    Get financial summary from finance module
    
    Query params:
        - start_date: YYYY-MM-DD (optional)
        - end_date: YYYY-MM-DD (optional)
    """
    sacco = get_object_or_404(SaccoOrganization, id=sacco_id)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if start_date:
        from django.utils.dateparse import parse_date
        start_date = parse_date(start_date)
    if end_date:
        from django.utils.dateparse import parse_date
        end_date = parse_date(end_date)
    
    summary = FinanceIntegrationService.get_sacco_financial_summary(
        sacco=sacco,
        start_date=start_date,
        end_date=end_date
    )
    
    return Response(summary)
