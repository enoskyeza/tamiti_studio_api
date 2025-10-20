from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from datetime import timedelta


class AnalyticsService:
    """
    Service for analytics and dashboard metrics
    Phase 5: Integration & Reporting
    """
    
    @staticmethod
    def get_dashboard_metrics(sacco):
        """
        Get key metrics for SACCO dashboard
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Dashboard metrics
        """
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        
        # Member metrics
        total_members = sacco.members.filter(status='active').count()
        new_members_this_month = sacco.members.filter(
            date_joined__gte=this_month_start,
            status='active'
        ).count()
        
        # Meeting metrics
        meetings_this_month = sacco.weekly_meetings.filter(
            meeting_date__gte=this_month_start,
            status='completed'
        ).count()
        
        total_collected_this_month = sacco.weekly_meetings.filter(
            meeting_date__gte=this_month_start,
            status='completed'
        ).aggregate(total=Sum('total_collected'))['total'] or Decimal('0')
        
        # Loan metrics
        active_loans = sacco.loans.filter(status__in=['disbursed', 'active'])
        total_loans_outstanding = sum(loan.total_balance for loan in active_loans)
        
        loans_this_month = sacco.loans.filter(
            disbursement_date__gte=this_month_start
        ).count()
        
        # Savings metrics
        from saccos.models import PassbookSection
        savings_sections = PassbookSection.objects.filter(
            sacco=sacco,
            section_type='savings',
            is_active=True
        )
        
        total_savings = Decimal('0')
        for member in sacco.members.filter(status='active'):
            passbook = member.get_passbook()
            for section in savings_sections:
                balance = passbook.get_section_balance(section)
                total_savings += balance
        
        # Overdue loans
        overdue_loans = [loan for loan in active_loans if loan.is_overdue]
        
        return {
            'members': {
                'total': total_members,
                'new_this_month': new_members_this_month
            },
            'meetings': {
                'this_month': meetings_this_month,
                'total_collected': total_collected_this_month
            },
            'loans': {
                'active': active_loans.count(),
                'outstanding_amount': total_loans_outstanding,
                'disbursed_this_month': loans_this_month,
                'overdue': len(overdue_loans)
            },
            'savings': {
                'total': total_savings,
                'per_member': total_savings / total_members if total_members > 0 else Decimal('0')
            }
        }
    
    @staticmethod
    def get_trend_analysis(sacco, months=6):
        """
        Get trend analysis for the past N months
        
        Args:
            sacco: SaccoOrganization instance
            months: Number of months to analyze
            
        Returns:
            dict: Trend data
        """
        today = timezone.now().date()
        trends = []
        
        for i in range(months):
            # Calculate month boundaries
            month_end = today.replace(day=1) - timedelta(days=i*30)
            month_start = month_end.replace(day=1)
            
            # Get metrics for this month
            meetings = sacco.weekly_meetings.filter(
                meeting_date__gte=month_start,
                meeting_date__lte=month_end,
                status='completed'
            )
            
            total_collected = meetings.aggregate(
                total=Sum('total_collected')
            )['total'] or Decimal('0')
            
            loans_disbursed = sacco.loans.filter(
                disbursement_date__gte=month_start,
                disbursement_date__lte=month_end
            ).count()
            
            avg_attendance = meetings.aggregate(
                avg=Avg('members_present')
            )['avg'] or 0
            
            trends.append({
                'month': month_start.strftime('%Y-%m'),
                'meetings': meetings.count(),
                'total_collected': float(total_collected),
                'loans_disbursed': loans_disbursed,
                'avg_attendance': round(avg_attendance, 1)
            })
        
        return {
            'period': f'Last {months} months',
            'trends': list(reversed(trends))
        }
    
    @staticmethod
    def get_member_growth_analysis(sacco):
        """
        Analyze member growth over time
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Growth analysis
        """
        members = sacco.members.all().order_by('date_joined')
        
        if not members:
            return {'error': 'No members'}
        
        # Growth by month
        first_member = members.first()
        start_date = first_member.date_joined.replace(day=1)
        today = timezone.now().date()
        
        monthly_growth = []
        current = start_date
        cumulative = 0
        
        while current <= today:
            next_month = (current + timedelta(days=32)).replace(day=1)
            
            new_members = members.filter(
                date_joined__gte=current,
                date_joined__lt=next_month
            ).count()
            
            cumulative += new_members
            
            monthly_growth.append({
                'month': current.strftime('%Y-%m'),
                'new_members': new_members,
                'total_members': cumulative
            })
            
            current = next_month
        
        return {
            'total_members': members.count(),
            'active_members': members.filter(status='active').count(),
            'first_member_date': first_member.date_joined,
            'monthly_growth': monthly_growth
        }
    
    @staticmethod
    def get_loan_performance_metrics(sacco):
        """
        Analyze loan portfolio performance
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Performance metrics
        """
        all_loans = sacco.loans.all()
        active_loans = all_loans.filter(status__in=['disbursed', 'active'])
        paid_loans = all_loans.filter(status='paid')
        
        # Calculate metrics
        total_disbursed = all_loans.filter(
            status__in=['disbursed', 'active', 'paid']
        ).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0')
        
        total_collected = sum(
            loan.amount_paid_principal + loan.amount_paid_interest
            for loan in all_loans
        )
        
        # Default rate
        defaulted_loans = all_loans.filter(status='defaulted').count()
        default_rate = (
            defaulted_loans / all_loans.count() * 100
        ) if all_loans.count() > 0 else 0
        
        # Portfolio at risk (overdue loans)
        overdue_loans = [loan for loan in active_loans if loan.is_overdue]
        portfolio_at_risk = sum(loan.total_balance for loan in overdue_loans)
        par_ratio = (
            portfolio_at_risk / total_disbursed * 100
        ) if total_disbursed > 0 else 0
        
        # Average loan size
        avg_loan_size = all_loans.filter(
            status__in=['disbursed', 'active', 'paid']
        ).aggregate(avg=Avg('principal_amount'))['avg'] or Decimal('0')
        
        # Repayment rate
        expected_repayment = sum(
            loan.total_amount for loan in all_loans
            if loan.status in ['active', 'paid', 'disbursed']
        )
        repayment_rate = (
            total_collected / expected_repayment * 100
        ) if expected_repayment > 0 else 0
        
        return {
            'portfolio_summary': {
                'total_loans': all_loans.count(),
                'active_loans': active_loans.count(),
                'paid_loans': paid_loans.count(),
                'defaulted_loans': defaulted_loans
            },
            'financial_metrics': {
                'total_disbursed': total_disbursed,
                'total_collected': total_collected,
                'outstanding': sum(loan.total_balance for loan in active_loans),
                'avg_loan_size': avg_loan_size
            },
            'risk_metrics': {
                'default_rate': round(default_rate, 2),
                'portfolio_at_risk': portfolio_at_risk,
                'par_ratio': round(par_ratio, 2),
                'overdue_loans': len(overdue_loans)
            },
            'performance': {
                'repayment_rate': round(repayment_rate, 2)
            }
        }
    
    @staticmethod
    def get_savings_growth_analysis(sacco):
        """
        Analyze savings growth over time
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Savings growth data
        """
        from saccos.models import PassbookSection
        
        # Get all meetings to track savings over time
        meetings = sacco.weekly_meetings.filter(
            status='completed'
        ).order_by('meeting_date')
        
        if not meetings:
            return {'error': 'No completed meetings'}
        
        savings_sections = PassbookSection.objects.filter(
            sacco=sacco,
            section_type='savings',
            is_active=True
        )
        
        # Track cumulative savings
        cumulative_data = []
        cumulative_total = Decimal('0')
        
        for meeting in meetings:
            # Add savings from this meeting
            cumulative_total += meeting.amount_to_bank
            
            cumulative_data.append({
                'date': meeting.meeting_date,
                'week': meeting.week_number,
                'amount_saved': float(meeting.amount_to_bank),
                'cumulative_savings': float(cumulative_total)
            })
        
        # Current total savings
        current_total = Decimal('0')
        for member in sacco.members.filter(status='active'):
            passbook = member.get_passbook()
            for section in savings_sections:
                current_total += passbook.get_section_balance(section)
        
        return {
            'current_total_savings': current_total,
            'total_members': sacco.members.filter(status='active').count(),
            'avg_per_member': current_total / sacco.members.filter(status='active').count()
            if sacco.members.filter(status='active').count() > 0 else Decimal('0'),
            'growth_data': cumulative_data[-26:] if len(cumulative_data) > 26 else cumulative_data  # Last 6 months
        }
    
    @staticmethod
    def get_meeting_efficiency_metrics(sacco, months=3):
        """
        Analyze meeting efficiency
        
        Args:
            sacco: SaccoOrganization instance
            months: Number of months to analyze
            
        Returns:
            dict: Efficiency metrics
        """
        today = timezone.now().date()
        start_date = today - timedelta(days=months * 30)
        
        meetings = sacco.weekly_meetings.filter(
            meeting_date__gte=start_date,
            status='completed'
        )
        
        if not meetings:
            return {'error': 'No meetings in this period'}
        
        total_members = sacco.members.filter(status='active').count()
        
        # Calculate averages
        avg_attendance = meetings.aggregate(
            avg=Avg('members_present')
        )['avg'] or 0
        
        avg_collection = meetings.aggregate(
            avg=Avg('total_collected')
        )['avg'] or Decimal('0')
        
        attendance_rate = (avg_attendance / total_members * 100) if total_members > 0 else 0
        
        # On-time meetings (held on expected day)
        # Assuming meetings should be held weekly
        expected_meetings = (today - start_date).days // 7
        actual_meetings = meetings.count()
        meeting_consistency = (actual_meetings / expected_meetings * 100) if expected_meetings > 0 else 0
        
        return {
            'period': f'Last {months} months',
            'total_meetings': actual_meetings,
            'expected_meetings': expected_meetings,
            'meeting_consistency': round(meeting_consistency, 2),
            'average_attendance': round(avg_attendance, 1),
            'attendance_rate': round(attendance_rate, 2),
            'average_collection': avg_collection,
            'total_collected': meetings.aggregate(
                total=Sum('total_collected')
            )['total'] or Decimal('0')
        }
