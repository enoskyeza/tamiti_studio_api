from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import (
    SaccoOrganization, SaccoMember, MemberPassbook,
    PassbookSection, PassbookEntry, DeductionRule,
    CashRoundSchedule, WeeklyMeeting, WeeklyContribution,
    SaccoLoan, LoanPayment, LoanGuarantor, SaccoEmergencySupport
)
from .serializers import (
    SaccoOrganizationSerializer, SaccoMemberSerializer, SaccoMemberListSerializer,
    MemberPassbookSerializer, PassbookSectionSerializer,
    PassbookEntrySerializer, DeductionRuleSerializer,
    PassbookStatementSerializer,
    CashRoundScheduleSerializer, WeeklyMeetingSerializer,
    WeeklyContributionSerializer,
    SaccoLoanSerializer, LoanPaymentSerializer,
    LoanGuarantorSerializer, SaccoEmergencySupportSerializer
)
from .services.passbook_service import PassbookService


class SaccoOrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SACCO Organization management
    Phase 1: Foundation
    """
    queryset = SaccoOrganization.objects.all()
    serializer_class = SaccoOrganizationSerializer
    permission_classes = [IsAuthenticated]
    lookup_value_regex = r'\d+'
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Super admins see all SACCOs
        if user.is_superuser or user.role == 'Admin':
            return SaccoOrganization.objects.all()
        
        # SACCO admins see only their SACCOs
        return user.administered_saccos.all()
    
    @action(detail=False, methods=['get'], url_path='my-saccos')
    def my_saccos(self, request):
        """Get all SACCOs the user has access to"""
        user = request.user
        
        # Get SACCOs where user is admin
        saccos = user.administered_saccos.all()
        
        # Also check if user is a member
        if hasattr(user, 'sacco_membership'):
            member_sacco = user.sacco_membership.sacco
            if member_sacco not in saccos:
                saccos = saccos | SaccoOrganization.objects.filter(id=member_sacco.id)
        
        serializer = self.get_serializer(saccos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='my-membership')
    def my_membership(self, request, pk=None):
        """Get user's membership in this SACCO"""
        sacco = self.get_object()
        user = request.user
        
        try:
            membership = SaccoMember.objects.get(user=user, sacco=sacco)
            serializer = SaccoMemberSerializer(membership)
            return Response(serializer.data)
        except SaccoMember.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this SACCO'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def create_default_sections(self, request, pk=None):
        """Create default passbook sections for a SACCO"""
        sacco = self.get_object()
        sections = PassbookSection.create_default_sections(sacco)
        
        serializer = PassbookSectionSerializer(sections, many=True)
        return Response({
            'message': f'Created {len(sections)} default sections',
            'sections': serializer.data
        }, status=status.HTTP_201_CREATED)


class SaccoMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SACCO Member management
    Phase 1: Foundation
    
    Supports both:
    - /api/saccos/{sacco_pk}/members/ (nested)
    - /api/saccos/members/?sacco={id} (flat)
    """
    queryset = SaccoMember.objects.all()
    serializer_class = SaccoMemberSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Use flattened serializer for list and retrieve views"""
        if self.action in ['list', 'retrieve']:
            return SaccoMemberListSerializer
        return SaccoMemberSerializer
    
    def get_queryset(self):
        """Filter members by SACCO"""
        # Check nested route parameter first
        sacco_id = self.kwargs.get('sacco_pk')
        
        # Fall back to query parameter
        if not sacco_id:
            sacco_id = self.request.query_params.get('sacco')
        
        if sacco_id:
            queryset = SaccoMember.objects.filter(sacco_id=sacco_id).select_related('user', 'sacco')
            
            # Apply search filter if provided
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    user__first_name__icontains=search
                ) | queryset.filter(
                    user__last_name__icontains=search
                ) | queryset.filter(
                    member_number__icontains=search
                )
            
            # Apply status filter if provided  
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            return queryset
        
        # If user is SACCO member, show only their SACCO
        if hasattr(self.request.user, 'sacco_membership'):
            return SaccoMember.objects.filter(
                sacco=self.request.user.sacco_membership.sacco
            ).select_related('user', 'sacco')
        
        return SaccoMember.objects.none()
    
    def perform_create(self, serializer):
        """Auto-create passbook when member is created"""
        member = serializer.save()
        PassbookService.create_passbook(member)
    
    def create(self, request, *args, **kwargs):
        """
        Create member with simplified serializer
        Auto-generates user credentials from first name only
        """
        from .serializers_account import SimplifiedMemberCreateSerializer
        
        # Get SACCO from nested route or query param
        sacco_id = kwargs.get('sacco_pk') or request.data.get('sacco')
        if not sacco_id:
            return Response(
                {'error': 'SACCO ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            sacco = SaccoOrganization.objects.get(id=sacco_id)
        except SaccoOrganization.DoesNotExist:
            return Response(
                {'error': 'SACCO not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Use simplified serializer
        serializer = SimplifiedMemberCreateSerializer(
            data=request.data,
            context={'sacco': sacco}
        )
        
        if serializer.is_valid():
            result = serializer.save()
            member = result['member']
            user = result['user']
            
            # Return member data with generated credentials
            member_serializer = SaccoMemberListSerializer(member)
            
            return Response({
                'message': 'Member created successfully',
                'member': member_serializer.data,
                'credentials': {
                    'username': result['generated_username'],
                    'password': result['generated_password'],
                },
                'instructions': f"Member can login with username '{result['generated_username']}' and password '{result['generated_password']}'. They should change their password after first login."
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def passbook(self, request, pk=None):
        """Get member's passbook"""
        member = self.get_object()
        passbook = member.get_passbook()
        serializer = MemberPassbookSerializer(passbook)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a suspended member"""
        member = self.get_object()
        member.status = 'active'
        member.save()
        return Response({'message': 'Member activated successfully'})
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend a member"""
        member = self.get_object()
        member.status = 'suspended'
        member.save()
        return Response({'message': 'Member suspended successfully'})
    
    @action(detail=False, methods=['get'])
    def me(self, request, sacco_pk=None):
        """Get current user's member profile"""
        try:
            # Get member for current user and specified SACCO
            member = SaccoMember.objects.select_related('user', 'sacco').get(
                user=request.user,
                sacco_id=sacco_pk
            )
            serializer = SaccoMemberListSerializer(member)
            return Response(serializer.data)
        except SaccoMember.DoesNotExist:
            return Response(
                {'error': 'You are not a member of this SACCO'},
                status=status.HTTP_404_NOT_FOUND
            )


class MemberPassbookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Member Passbook (read-only, entries are created via PassbookEntryViewSet)
    Phase 2: Passbook System
    """
    queryset = MemberPassbook.objects.all()
    serializer_class = MemberPassbookSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter passbooks by SACCO"""
        if hasattr(self.request.user, 'sacco_membership'):
            return MemberPassbook.objects.filter(sacco=self.request.user.sacco_membership.sacco)
        return MemberPassbook.objects.none()
    
    @action(detail=True, methods=['get'])
    def balances(self, request, pk=None):
        """Get all section balances for a passbook"""
        passbook = self.get_object()
        balances = PassbookService.get_all_balances(passbook)
        return Response(balances)
    
    @action(detail=True, methods=['post'])
    def statement(self, request, pk=None):
        """Generate passbook statement"""
        passbook = self.get_object()
        serializer = PassbookStatementSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        section = None
        if 'section_id' in data:
            section = get_object_or_404(PassbookSection, id=data['section_id'])
        
        statement = PassbookService.generate_statement(
            passbook=passbook,
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            section=section
        )
        
        return Response(statement)


class PassbookSectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Passbook Section management
    Phase 2: Passbook System
    """
    queryset = PassbookSection.objects.all()
    serializer_class = PassbookSectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter sections by SACCO"""
        sacco_id = self.kwargs.get('sacco_pk') or self.request.query_params.get('sacco')
        
        if sacco_id:
            return PassbookSection.objects.filter(sacco_id=sacco_id, is_active=True)
        
        if hasattr(self.request.user, 'sacco_membership'):
            return PassbookSection.objects.filter(
                sacco=self.request.user.sacco_membership.sacco,
                is_active=True
            )
        
        return PassbookSection.objects.none()


class PassbookEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Passbook Entry management
    Phase 2: Passbook System
    """
    queryset = PassbookEntry.objects.all()
    serializer_class = PassbookEntrySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter entries by passbook, meeting, section, or member"""
        queryset = PassbookEntry.objects.all().select_related('passbook', 'section', 'passbook__member')
        
        # Filter by passbook
        passbook_id = self.kwargs.get('passbook_pk') or self.request.query_params.get('passbook')
        if passbook_id:
            queryset = queryset.filter(passbook_id=passbook_id)
        
        # Filter by meeting
        meeting_id = self.request.query_params.get('meeting')
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        
        # Filter by section
        section_id = self.request.query_params.get('section')
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        
        # Filter by member
        member_id = self.request.query_params.get('member')
        if member_id:
            queryset = queryset.filter(passbook__member_id=member_id)
        
        # Order by date descending (most recent first)
        queryset = queryset.order_by('-transaction_date', '-created_at')
        
        # If no filters provided, return empty
        if not any([passbook_id, meeting_id, section_id, member_id]):
            return PassbookEntry.objects.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """Record entry using PassbookService"""
        data = serializer.validated_data
        
        entry = PassbookService.record_entry(
            passbook=data['passbook'],
            section=data['section'],
            amount=data['amount'],
            transaction_type=data['transaction_type'],
            description=data['description'],
            recorded_by=self.request.user,
            transaction_date=data.get('transaction_date'),
            reference_number=data.get('reference_number', ''),
            week_number=data.get('week_number'),
            meeting=data.get('meeting')  # Pass meeting field
        )
        
        # Return the created entry
        serializer.instance = entry
    
    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """Create a reversal entry"""
        entry = self.get_object()
        reason = request.data.get('reason', 'No reason provided')
        
        reversal = PassbookService.reverse_entry(
            entry=entry,
            recorded_by=request.user,
            reason=reason
        )
        
        serializer = self.get_serializer(reversal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DeductionRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Deduction Rule management
    Phase 2: Passbook System
    """
    queryset = DeductionRule.objects.all()
    serializer_class = DeductionRuleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter deduction rules by SACCO"""
        sacco_id = self.kwargs.get('sacco_pk') or self.request.query_params.get('sacco')
        
        if sacco_id:
            return DeductionRule.objects.filter(sacco_id=sacco_id)
        
        if hasattr(self.request.user, 'sacco_membership'):
            return DeductionRule.objects.filter(sacco=self.request.user.sacco_membership.sacco)
        
        return DeductionRule.objects.none()
    
    def perform_create(self, serializer):
        """Automatically set amount from section's weekly_amount"""
        section = serializer.validated_data.get('section')
        if section and section.weekly_amount:
            serializer.save(amount=section.weekly_amount)
        else:
            serializer.save()
    
    def perform_update(self, serializer):
        """Automatically update amount from section's weekly_amount if section changed"""
        section = serializer.validated_data.get('section')
        if section and section.weekly_amount:
            serializer.save(amount=section.weekly_amount)
        else:
            serializer.save()


# ============================================================================
# PHASE 3: WEEKLY MEETINGS VIEWS
# ============================================================================


class CashRoundScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Cash Round Schedule management
    Phase 3: Weekly Meetings
    """
    queryset = CashRoundSchedule.objects.all()
    serializer_class = CashRoundScheduleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter schedules by SACCO"""
        sacco_id = self.kwargs.get('sacco_pk') or self.request.query_params.get('sacco')
        
        if sacco_id:
            return CashRoundSchedule.objects.filter(sacco_id=sacco_id)
        
        if hasattr(self.request.user, 'sacco_membership'):
            return CashRoundSchedule.objects.filter(sacco=self.request.user.sacco_membership.sacco)
        
        return CashRoundSchedule.objects.none()
    
    def perform_create(self, serializer):
        """Ensure nested SACCO creation works"""
        sacco_id = self.kwargs.get('sacco_pk')
        
        if sacco_id:
            serializer.save(sacco_id=sacco_id)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def advance(self, request, pk=None):
        """Advance to next member in rotation"""
        schedule = self.get_object()
        schedule.advance_to_next_member()
        
        serializer = self.get_serializer(schedule)
        return Response(serializer.data)


class WeeklyMeetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Weekly Meeting management
    Phase 3: Weekly Meetings
    """
    queryset = WeeklyMeeting.objects.all()
    serializer_class = WeeklyMeetingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter meetings by SACCO"""
        sacco_id = self.kwargs.get('sacco_pk') or self.request.query_params.get('sacco')
        year = self.request.query_params.get('year')
        
        queryset = WeeklyMeeting.objects.all()
        
        if sacco_id:
            queryset = queryset.filter(sacco_id=sacco_id)
        elif hasattr(self.request.user, 'sacco_membership'):
            queryset = queryset.filter(sacco=self.request.user.sacco_membership.sacco)
        else:
            return WeeklyMeeting.objects.none()
        
        if year:
            queryset = queryset.filter(year=year)
        
        return queryset
    
    def perform_create(self, serializer):
        """Ensure nested SACCO creation works"""
        sacco_id = self.kwargs.get('sacco_pk')
        
        if sacco_id:
            serializer.save(sacco_id=sacco_id, recorded_by=self.request.user)
        else:
            serializer.save(recorded_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process_deductions(self, request, pk=None):
        """Process deductions for the meeting"""
        from saccos.services.weekly_meeting_service import WeeklyMeetingService
        
        meeting = self.get_object()
        
        result = WeeklyMeetingService.process_weekly_deductions(
            meeting=meeting,
            recorded_by=request.user
        )
        
        if result['success']:
            serializer = self.get_serializer(meeting)
            return Response({
                'meeting': serializer.data,
                **result
            })
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark meeting as completed"""
        from saccos.services.weekly_meeting_service import WeeklyMeetingService
        
        meeting = self.get_object()
        
        meeting = WeeklyMeetingService.complete_meeting(
            meeting=meeting,
            recorded_by=request.user
        )
        
        serializer = self.get_serializer(meeting)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        """Finalize meeting: process deductions and mark as completed"""
        from saccos.services.weekly_meeting_service import WeeklyMeetingService
        
        meeting = self.get_object()
        
        # First process deductions for recipient
        deduction_result = WeeklyMeetingService.process_weekly_deductions(
            meeting=meeting,
            recorded_by=request.user
        )
        
        # Then mark as completed
        meeting = WeeklyMeetingService.complete_meeting(
            meeting=meeting,
            recorded_by=request.user
        )
        
        serializer = self.get_serializer(meeting)
        return Response({
            'meeting': serializer.data,
            'deductions_processed': deduction_result.get('success', False),
            'entries_created': deduction_result.get('entries_created', 0)
        })
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get meeting summary"""
        from saccos.services.weekly_meeting_service import WeeklyMeetingService
        
        meeting = self.get_object()
        summary = WeeklyMeetingService.get_meeting_summary(meeting)
        
        return Response(summary)


class WeeklyContributionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Weekly Contribution management
    Phase 3: Weekly Meetings
    """
    queryset = WeeklyContribution.objects.all()
    serializer_class = WeeklyContributionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter contributions by meeting"""
        meeting_id = self.request.query_params.get('meeting')
        
        if meeting_id:
            return WeeklyContribution.objects.filter(meeting_id=meeting_id)
        
        return WeeklyContribution.objects.none()
    
    def perform_create(self, serializer):
        """Save and recalculate deductions"""
        contribution = serializer.save()
        
        if contribution.is_recipient:
            contribution.calculate_total_deductions()
            contribution.save()
        
        # Recalculate meeting totals
        contribution.meeting.calculate_totals()


# ============================================================================
# PHASE 4: LOAN MANAGEMENT VIEWS
# ============================================================================


class SaccoLoanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SACCO Loan management
    Phase 4: Loan Management
    """
    queryset = SaccoLoan.objects.all()
    serializer_class = SaccoLoanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter loans by SACCO or member"""
        sacco_id = self.request.query_params.get('sacco')
        member_id = self.request.query_params.get('member')
        loan_status = self.request.query_params.get('status')
        
        queryset = SaccoLoan.objects.all()
        
        if sacco_id:
            queryset = queryset.filter(sacco_id=sacco_id)
        elif hasattr(self.request.user, 'sacco_membership'):
            queryset = queryset.filter(sacco=self.request.user.sacco_membership.sacco)
        else:
            return SaccoLoan.objects.none()
        
        if member_id:
            queryset = queryset.filter(member_id=member_id)
        
        if loan_status:
            queryset = queryset.filter(status=loan_status)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a loan"""
        from saccos.services.loan_service import LoanService
        
        loan = self.get_object()
        disbursement_date = request.data.get('disbursement_date')
        
        try:
            loan = LoanService.approve_loan(
                loan=loan,
                approved_by=request.user,
                disbursement_date=disbursement_date
            )
            
            serializer = self.get_serializer(loan)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a loan"""
        from saccos.services.loan_service import LoanService
        
        loan = self.get_object()
        rejection_reason = request.data.get('rejection_reason', '')
        
        try:
            loan = LoanService.reject_loan(
                loan=loan,
                rejected_by=request.user,
                rejection_reason=rejection_reason
            )
            
            serializer = self.get_serializer(loan)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def disburse(self, request, pk=None):
        """Disburse a loan"""
        from saccos.services.loan_service import LoanService
        
        loan = self.get_object()
        disbursement_date = request.data.get('disbursement_date')
        
        try:
            result = LoanService.disburse_loan(
                loan=loan,
                disbursement_date=disbursement_date
            )
            
            serializer = self.get_serializer(result['loan'])
            return Response({
                'loan': serializer.data,
                'passbook_entry': result.get('passbook_entry')
            })
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get loan summary"""
        from saccos.services.loan_service import LoanService
        
        loan = self.get_object()
        summary = LoanService.get_loan_summary(loan)
        
        return Response(summary)


class LoanPaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Loan Payment management
    Phase 4: Loan Management
    """
    queryset = LoanPayment.objects.all()
    serializer_class = LoanPaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter payments by loan"""
        loan_id = self.request.query_params.get('loan')
        
        if loan_id:
            return LoanPayment.objects.filter(loan_id=loan_id)
        
        return LoanPayment.objects.none()
    
    def perform_create(self, serializer):
        """Record payment using LoanService"""
        from saccos.services.loan_service import LoanService
        
        loan_id = self.request.data.get('loan')
        loan = get_object_or_404(SaccoLoan, id=loan_id)
        
        result = LoanService.record_loan_payment(
            loan=loan,
            payment_amount=self.request.data.get('total_amount'),
            payment_date=self.request.data.get('payment_date'),
            recorded_by=self.request.user,
            payment_method=self.request.data.get('payment_method', ''),
            reference_number=self.request.data.get('reference_number', ''),
            notes=self.request.data.get('notes', '')
        )
        
        serializer.instance = result['payment']


class LoanGuarantorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Loan Guarantor management
    Phase 4: Loan Management
    """
    queryset = LoanGuarantor.objects.all()
    serializer_class = LoanGuarantorSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter guarantors by loan"""
        loan_id = self.request.query_params.get('loan')
        
        if loan_id:
            return LoanGuarantor.objects.filter(loan_id=loan_id)
        
        return LoanGuarantor.objects.none()


class SaccoEmergencySupportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Emergency Support management
    Phase 4: Loan Management
    """
    queryset = SaccoEmergencySupport.objects.all()
    serializer_class = SaccoEmergencySupportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter emergency support by SACCO or member"""
        sacco_id = self.request.query_params.get('sacco')
        member_id = self.request.query_params.get('member')
        
        queryset = SaccoEmergencySupport.objects.all()
        
        if sacco_id:
            queryset = queryset.filter(sacco_id=sacco_id)
        elif hasattr(self.request.user, 'sacco_membership'):
            queryset = queryset.filter(sacco=self.request.user.sacco_membership.sacco)
        else:
            return SaccoEmergencySupport.objects.none()
        
        if member_id:
            queryset = queryset.filter(member_id=member_id)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve and disburse emergency support"""
        from saccos.services.loan_service import LoanService
        
        support = self.get_object()
        
        try:
            result = LoanService.approve_emergency_support(
                support=support,
                approved_by=request.user
            )
            
            serializer = self.get_serializer(result['support'])
            return Response({
                'support': serializer.data,
                'passbook_entry': result.get('passbook_entry')
            })
        
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
