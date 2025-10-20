from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from datetime import timedelta


class ReportingService:
    """
    Service for generating reports and analytics
    Phase 5: Integration & Reporting
    """
    
    @staticmethod
    def generate_member_statement(member, start_date=None, end_date=None):
        """
        Generate comprehensive statement for a member
        
        Args:
            member: SaccoMember instance
            start_date: Start date (defaults to 3 months ago)
            end_date: End date (defaults to today)
            
        Returns:
            dict: Complete member statement
        """
        from saccos.models import PassbookSection
        from saccos.services.passbook_service import PassbookService
        
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=90)
        
        passbook = member.get_passbook()
        
        # Get passbook statement
        statement = PassbookService.generate_statement(
            passbook=passbook,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get loan summary
        loans = member.loans.all()
        active_loans = loans.filter(status__in=['disbursed', 'active'])
        
        loan_summary = {
            'total_loans': loans.count(),
            'active_loans': active_loans.count(),
            'total_borrowed': loans.aggregate(
                total=Sum('principal_amount')
            )['total'] or Decimal('0'),
            'total_outstanding': sum(
                loan.total_balance for loan in active_loans
            ),
            'loans': [
                {
                    'loan_number': loan.loan_number,
                    'principal': loan.principal_amount,
                    'balance': loan.total_balance,
                    'status': loan.status,
                    'due_date': loan.due_date
                }
                for loan in active_loans
            ]
        }
        
        # Get meeting attendance
        contributions = member.weekly_contributions.filter(
            meeting__meeting_date__gte=start_date,
            meeting__meeting_date__lte=end_date
        )
        
        attendance = {
            'meetings_attended': contributions.filter(was_present=True).count(),
            'meetings_missed': contributions.filter(was_present=False).count(),
            'total_contributed': contributions.aggregate(
                total=Sum('amount_contributed')
            )['total'] or Decimal('0'),
            'cash_rounds_received': member.received_cash_rounds.filter(
                meeting_date__gte=start_date,
                meeting_date__lte=end_date,
                status='completed'
            ).count()
        }
        
        return {
            'member': {
                'member_number': member.member_number,
                'name': member.user.get_full_name(),
                'status': member.status,
                'date_joined': member.date_joined
            },
            'period': {
                'start': start_date,
                'end': end_date
            },
            'passbook': statement,
            'loans': loan_summary,
            'attendance': attendance,
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def generate_loan_portfolio_report(sacco, as_of_date=None):
        """
        Generate loan portfolio report
        
        Args:
            sacco: SaccoOrganization instance
            as_of_date: Report date (defaults to today)
            
        Returns:
            dict: Loan portfolio analysis
        """
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        loans = sacco.loans.all()
        
        # Status breakdown
        status_breakdown = {}
        for status in ['pending', 'approved', 'disbursed', 'active', 'paid', 'defaulted']:
            count = loans.filter(status=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        # Active loans analysis
        active_loans = loans.filter(status__in=['disbursed', 'active'])
        
        total_principal = active_loans.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        total_outstanding_principal = sum(
            loan.balance_principal for loan in active_loans
        )
        
        total_outstanding_interest = sum(
            loan.balance_interest for loan in active_loans
        )
        
        # Overdue loans
        overdue_loans = [loan for loan in active_loans if loan.is_overdue]
        
        # Repayment rate
        total_expected = sum(loan.total_amount for loan in active_loans)
        total_paid = sum(
            loan.amount_paid_principal + loan.amount_paid_interest
            for loan in active_loans
        )
        repayment_rate = (total_paid / total_expected * 100) if total_expected > 0 else 0
        
        return {
            'as_of_date': as_of_date,
            'summary': {
                'total_loans': loans.count(),
                'active_loans': active_loans.count(),
                'overdue_loans': len(overdue_loans),
                'total_principal_disbursed': total_principal,
                'total_outstanding_principal': total_outstanding_principal,
                'total_outstanding_interest': total_outstanding_interest,
                'total_outstanding': total_outstanding_principal + total_outstanding_interest,
                'repayment_rate': round(repayment_rate, 2)
            },
            'by_status': status_breakdown,
            'overdue_details': [
                {
                    'loan_number': loan.loan_number,
                    'member': loan.member.member_number,
                    'principal_balance': loan.balance_principal,
                    'interest_balance': loan.balance_interest,
                    'due_date': loan.due_date,
                    'days_overdue': (as_of_date - loan.due_date).days
                }
                for loan in overdue_loans
            ]
        }
    
    @staticmethod
    def generate_financial_statement(sacco, start_date, end_date):
        """
        Generate financial statement (Income & Expense)
        
        Args:
            sacco: SaccoOrganization instance
            start_date: Period start
            end_date: Period end
            
        Returns:
            dict: Financial statement
        """
        meetings = sacco.weekly_meetings.filter(
            meeting_date__gte=start_date,
            meeting_date__lte=end_date,
            status='completed'
        )
        
        # Income
        total_collected = meetings.aggregate(
            total=Sum('total_collected')
        )['total'] or Decimal('0')
        
        total_to_bank = meetings.aggregate(
            total=Sum('amount_to_bank')
        )['total'] or Decimal('0')
        
        # Loan interest collected
        loan_payments = sacco.loans.filter(
            payments__payment_date__gte=start_date,
            payments__payment_date__lte=end_date
        ).values_list('payments__interest_amount', flat=True)
        
        interest_income = sum(loan_payments) if loan_payments else Decimal('0')
        
        # Expenses (loans disbursed)
        loans_disbursed = sacco.loans.filter(
            disbursement_date__gte=start_date,
            disbursement_date__lte=end_date,
            status__in=['disbursed', 'active', 'paid']
        )
        
        total_loans_disbursed = loans_disbursed.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        # Emergency support
        emergency_disbursed = sacco.emergency_supports.filter(
            support_date__gte=start_date,
            support_date__lte=end_date,
            status='disbursed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'income': {
                'member_contributions': total_collected,
                'loan_interest': interest_income,
                'total_income': total_collected + interest_income
            },
            'expenses': {
                'loans_disbursed': total_loans_disbursed,
                'emergency_support': emergency_disbursed,
                'cash_rounds_paid': meetings.aggregate(
                    total=Sum('amount_to_recipient')
                )['total'] or Decimal('0'),
                'total_expenses': total_loans_disbursed + emergency_disbursed
            },
            'net': {
                'savings_to_bank': total_to_bank,
                'net_position': (total_collected + interest_income) - (total_loans_disbursed + emergency_disbursed)
            },
            'meetings': {
                'total_meetings': meetings.count(),
                'average_collection': total_collected / meetings.count() if meetings.count() > 0 else Decimal('0')
            }
        }
    
    @staticmethod
    def generate_attendance_report(sacco, start_date, end_date):
        """
        Generate member attendance report
        
        Args:
            sacco: SaccoOrganization instance
            start_date: Period start
            end_date: Period end
            
        Returns:
            dict: Attendance statistics
        """
        meetings = sacco.weekly_meetings.filter(
            meeting_date__gte=start_date,
            meeting_date__lte=end_date
        )
        
        total_meetings = meetings.count()
        if total_meetings == 0:
            return {'error': 'No meetings in this period'}
        
        members = sacco.members.filter(status='active')
        member_stats = []
        
        for member in members:
            contributions = member.weekly_contributions.filter(
                meeting__in=meetings
            )
            
            attended = contributions.filter(was_present=True).count()
            missed = contributions.filter(was_present=False).count()
            attendance_rate = (attended / total_meetings * 100) if total_meetings > 0 else 0
            
            member_stats.append({
                'member_number': member.member_number,
                'name': member.user.get_full_name(),
                'attended': attended,
                'missed': missed,
                'attendance_rate': round(attendance_rate, 2),
                'total_contributed': contributions.aggregate(
                    total=Sum('amount_contributed')
                )['total'] or Decimal('0')
            })
        
        # Sort by attendance rate
        member_stats.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'summary': {
                'total_meetings': total_meetings,
                'total_members': members.count(),
                'average_attendance_rate': round(
                    sum(m['attendance_rate'] for m in member_stats) / len(member_stats),
                    2
                ) if member_stats else 0
            },
            'members': member_stats
        }
    
    @staticmethod
    def generate_savings_report(sacco, start_date=None, end_date=None):
        """
        Generate savings accumulation report
        
        Args:
            sacco: SaccoOrganization instance
            start_date: Period start
            end_date: Period end
            
        Returns:
            dict: Savings report
        """
        from saccos.models import PassbookSection, PassbookEntry
        
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=365)  # Last year
        
        # Get savings sections
        savings_sections = PassbookSection.objects.filter(
            sacco=sacco,
            section_type='savings',
            is_active=True
        )
        
        members = sacco.members.filter(status='active')
        member_savings = []
        
        for member in members:
            passbook = member.get_passbook()
            total_savings = Decimal('0')
            
            for section in savings_sections:
                balance = PassbookEntry.objects.filter(
                    passbook=passbook,
                    section=section,
                    transaction_date__lte=end_date
                ).order_by('-created_at').first()
                
                if balance:
                    total_savings += balance.balance_after
            
            member_savings.append({
                'member_number': member.member_number,
                'name': member.user.get_full_name(),
                'total_savings': total_savings
            })
        
        # Sort by savings amount
        member_savings.sort(key=lambda x: x['total_savings'], reverse=True)
        
        total_sacco_savings = sum(m['total_savings'] for m in member_savings)
        
        return {
            'as_of_date': end_date,
            'summary': {
                'total_members': len(member_savings),
                'total_savings': total_sacco_savings,
                'average_per_member': total_sacco_savings / len(member_savings) if member_savings else Decimal('0')
            },
            'members': member_savings,
            'sections': [
                {
                    'name': section.name,
                    'type': section.section_type,
                    'is_compulsory': section.is_compulsory,
                    'weekly_amount': section.weekly_amount
                }
                for section in savings_sections
            ]
        }
    
    @staticmethod
    def generate_cash_round_report(sacco, year=None):
        """
        Generate cash round completion report
        
        Args:
            sacco: SaccoOrganization instance
            year: Year to report on (defaults to current year)
            
        Returns:
            dict: Cash round report
        """
        if not year:
            year = timezone.now().year
        
        meetings = sacco.weekly_meetings.filter(
            year=year,
            status='completed'
        ).order_by('meeting_date')
        
        # Get unique recipients
        recipients = {}
        for meeting in meetings:
            if meeting.cash_round_recipient:
                member_id = meeting.cash_round_recipient.id
                if member_id not in recipients:
                    recipients[member_id] = {
                        'member': meeting.cash_round_recipient,
                        'times_received': 0,
                        'total_received': Decimal('0'),
                        'dates': []
                    }
                recipients[member_id]['times_received'] += 1
                recipients[member_id]['total_received'] += meeting.amount_to_recipient
                recipients[member_id]['dates'].append(meeting.meeting_date)
        
        recipient_list = [
            {
                'member_number': data['member'].member_number,
                'name': data['member'].user.get_full_name(),
                'times_received': data['times_received'],
                'total_received': data['total_received'],
                'dates': data['dates']
            }
            for data in recipients.values()
        ]
        
        return {
            'year': year,
            'summary': {
                'total_meetings': meetings.count(),
                'total_distributed': meetings.aggregate(
                    total=Sum('amount_to_recipient')
                )['total'] or Decimal('0'),
                'unique_recipients': len(recipients)
            },
            'recipients': recipient_list
        }
    
    @staticmethod
    def generate_member_ranking_report(sacco):
        """
        Generate member ranking by various metrics
        
        Args:
            sacco: SaccoOrganization instance
            
        Returns:
            dict: Member rankings
        """
        members = sacco.members.filter(status='active')
        member_data = []
        
        for member in members:
            passbook = member.get_passbook()
            balances = passbook.get_all_balances()
            
            total_savings = sum(
                data['balance'] for name, data in balances.items()
                if data.get('section_type') == 'savings'
            )
            
            loans_taken = member.loans.count()
            active_loans = member.loans.filter(status__in=['disbursed', 'active']).count()
            
            contributions = member.weekly_contributions.all()
            attendance_rate = (
                contributions.filter(was_present=True).count() /
                contributions.count() * 100
            ) if contributions.count() > 0 else 0
            
            member_data.append({
                'member_number': member.member_number,
                'name': member.user.get_full_name(),
                'total_savings': total_savings,
                'loans_taken': loans_taken,
                'active_loans': active_loans,
                'attendance_rate': round(attendance_rate, 2),
                'date_joined': member.date_joined
            })
        
        return {
            'top_savers': sorted(member_data, key=lambda x: x['total_savings'], reverse=True)[:10],
            'best_attendance': sorted(member_data, key=lambda x: x['attendance_rate'], reverse=True)[:10],
            'most_loans': sorted(member_data, key=lambda x: x['loans_taken'], reverse=True)[:10]
        }
