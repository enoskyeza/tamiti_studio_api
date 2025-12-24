from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from dateutil.relativedelta import relativedelta


class LoanService:
    """
    Business logic for loan management
    Phase 4: Loan Management
    """
    
    @staticmethod
    @transaction.atomic
    def create_loan_application(
        sacco,
        member,
        principal_amount,
        interest_rate,
        duration_months,
        purpose,
        repayment_frequency='monthly',
        guarantor_ids=None,
        application_date=None,
        notes='',
    ):
        """
        Create a new loan application
        
        Args:
            sacco: SaccoOrganization instance
            member: SaccoMember applying for loan
            principal_amount: Loan amount requested
            interest_rate: Interest rate percentage
            duration_months: Loan duration in months
            purpose: Reason for loan
            guarantor_ids: List of guarantor member IDs
            application_date: Optional application date (defaults to today)
            notes: Optional free-form notes/description to store on the loan
            
        Returns:
            SaccoLoan instance
        """
        from saccos.models import SaccoLoan, LoanGuarantor, SaccoMember
        import re
        
        # Generate loan number using MAX to avoid UNIQUE constraint issues after deletions
        prefix = sacco.registration_number or 'LOAN'
        last_loan = SaccoLoan.objects.filter(
            sacco=sacco,
            loan_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_loan:
            # Extract the numeric suffix from the last loan number
            match = re.search(r'-(\d+)$', last_loan.loan_number)
            next_num = int(match.group(1)) + 1 if match else 1
        else:
            next_num = 1
        
        loan_number = f"{prefix}-{next_num:05d}"
        
        # Use provided application date or default to today
        if not application_date:
            application_date = timezone.now().date()
        elif isinstance(application_date, str):
            application_date = parse_date(application_date) or timezone.now().date()
        
        # Create loan
        loan = SaccoLoan(
            sacco=sacco,
            member=member,
            loan_number=loan_number,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            duration_months=duration_months,
            repayment_frequency=repayment_frequency,
            purpose=purpose,
            application_date=application_date,
            status='pending',
            notes=notes or '',
        )
        
        # Calculate interest
        loan.calculate_interest()
        loan.save()
        
        # Add guarantors
        if guarantor_ids:
            for guarantor_id in guarantor_ids:
                try:
                    guarantor = SaccoMember.objects.get(id=guarantor_id, sacco=sacco)
                    # Each guarantor guarantees equal portion
                    guarantee_amount = principal_amount / len(guarantor_ids)
                    
                    LoanGuarantor.objects.create(
                        loan=loan,
                        guarantor=guarantor,
                        guarantee_amount=guarantee_amount
                    )
                except SaccoMember.DoesNotExist:
                    pass
        
        return loan
    
    @staticmethod
    @transaction.atomic
    def approve_loan(loan, approved_by, disbursement_date=None):
        """
        Approve a loan application
        
        Args:
            loan: SaccoLoan instance
            approved_by: User approving the loan
            disbursement_date: Optional disbursement date
            
        Returns:
            Updated loan
        """
        if loan.status != 'pending':
            raise ValueError(f"Cannot approve loan with status: {loan.status}")
        
        loan.status = 'approved'
        loan.approved_by = approved_by
        loan.approval_date = timezone.now().date()
        
        if disbursement_date:
            # Convert string dates from API to date objects
            if isinstance(disbursement_date, str):
                parsed = parse_date(disbursement_date)
                if not parsed:
                    raise ValueError("Invalid disbursement date format; expected YYYY-MM-DD")
                disbursement_date = parsed
            loan.disbursement_date = disbursement_date
            loan.due_date = disbursement_date + relativedelta(months=loan.duration_months)
            loan.status = 'disbursed'
        
        loan.save()
        return loan
    
    @staticmethod
    @transaction.atomic
    def disburse_loan(loan, disbursement_date=None):
        """
        Disburse an approved loan
        
        Args:
            loan: SaccoLoan instance
            disbursement_date: Date of disbursement (defaults to today)
            
        Returns:
            dict with loan and passbook entry
        """
        from saccos.models import PassbookSection
        from saccos.services.passbook_service import PassbookService
        
        if loan.status not in ['approved', 'disbursed']:
            raise ValueError(f"Cannot disburse loan with status: {loan.status}")
        
        if not disbursement_date:
            disbursement_date = timezone.now().date()
        elif isinstance(disbursement_date, str):
            parsed = parse_date(disbursement_date)
            if not parsed:
                raise ValueError("Invalid disbursement date format; expected YYYY-MM-DD")
            disbursement_date = parsed
        
        loan.disbursement_date = disbursement_date
        loan.due_date = disbursement_date + relativedelta(months=loan.duration_months)
        # Mark loan as disbursed so payments are allowed
        loan.status = 'disbursed'
        loan.save()
        
        # Record in passbook (debit from loan section)
        try:
            loan_section = PassbookSection.objects.get(
                sacco=loan.sacco,
                section_type='loan'
            )
            
            passbook = loan.member.get_passbook()
            
            entry = PassbookService.record_entry(
                passbook=passbook,
                section=loan_section,
                amount=loan.principal_amount,
                transaction_type='debit',
                description=f'Loan disbursed - {loan.loan_number}',
                recorded_by=loan.approved_by,
                transaction_date=disbursement_date,
                reference_number=loan.loan_number
            )
            
            return {
                'loan': loan,
                'passbook_entry': entry
            }
        
        except PassbookSection.DoesNotExist:
            return {
                'loan': loan,
                'passbook_entry': None,
                'warning': 'No loan section found in passbook'
            }
    
    @staticmethod
    @transaction.atomic
    def record_loan_payment(
        loan,
        payment_amount,
        payment_date,
        recorded_by,
        payment_method='',
        reference_number='',
        notes=''
    ):
        """
        Record a payment towards a loan
        
        Automatically splits payment between interest and principal:
        - Pay interest first
        - Remaining goes to principal
        
        Args:
            loan: SaccoLoan instance
            payment_amount: Total payment amount
            payment_date: Date of payment
            recorded_by: User recording payment
            payment_method: Payment method
            reference_number: Payment reference
            notes: Optional notes
            
        Returns:
            dict with payment and passbook entry
        """
        from saccos.models import LoanPayment, PassbookSection
        from saccos.services.passbook_service import PassbookService
        
        if loan.status not in ['disbursed', 'active']:
            raise ValueError(f"Cannot record payment for loan with status: {loan.status}")
        
        # Coerce payment amount to Decimal (may come in as string from API)
        if not payment_amount:
            raise ValueError("Payment amount is required")
        payment_amount = Decimal(str(payment_amount))
        
        # Split payment: interest first, then principal
        interest_due = loan.balance_interest
        principal_due = loan.balance_principal
        
        if payment_amount <= interest_due:
            # Payment covers only interest (or part of it)
            interest_amount = payment_amount
            principal_amount = Decimal('0')
        else:
            # Payment covers all interest + some principal
            interest_amount = interest_due
            principal_amount = min(payment_amount - interest_due, principal_due)
        
        # Create payment record
        payment = LoanPayment.objects.create(
            loan=loan,
            payment_date=payment_date,
            total_amount=interest_amount + principal_amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
            recorded_by=recorded_by
        )
        
        # Record in passbook (credit to loan section for principal)
        passbook_entry = None
        if principal_amount > 0:
            try:
                loan_section = PassbookSection.objects.get(
                    sacco=loan.sacco,
                    section_type='loan'
                )
                
                passbook = loan.member.get_passbook()
                
                passbook_entry = PassbookService.record_entry(
                    passbook=passbook,
                    section=loan_section,
                    amount=principal_amount,
                    transaction_type='credit',
                    description=f'Loan payment - {loan.loan_number}',
                    recorded_by=recorded_by,
                    transaction_date=payment_date,
                    reference_number=reference_number or payment.id
                )
                
                payment.passbook_entry = passbook_entry
                payment.save()
            
            except PassbookSection.DoesNotExist:
                pass
        
        # Record interest in interest section if any
        if interest_amount > 0:
            try:
                interest_section = PassbookSection.objects.get(
                    sacco=loan.sacco,
                    section_type='interest'
                )
                
                passbook = loan.member.get_passbook()
                
                interest_entry = PassbookService.record_entry(
                    passbook=passbook,
                    section=interest_section,
                    amount=interest_amount,
                    transaction_type='credit',
                    description=f'Interest payment - {loan.loan_number}',
                    recorded_by=recorded_by,
                    transaction_date=payment_date,
                    reference_number=reference_number or payment.id
                )
            
            except PassbookSection.DoesNotExist:
                pass
        
        # Loan balances are auto-updated in LoanPayment.save()
        
        return {
            'payment': payment,
            'passbook_entry': passbook_entry,
            'remaining_balance': loan.total_balance,
            'is_paid_off': loan.status == 'paid'
        }
    
    @staticmethod
    @transaction.atomic
    def reject_loan(loan, rejected_by, rejection_reason=''):
        """
        Reject a loan application
        
        Args:
            loan: SaccoLoan instance
            rejected_by: User rejecting the loan
            rejection_reason: Optional reason for rejection
            
        Returns:
            Updated loan
        """
        if loan.status != 'pending':
            raise ValueError(f"Cannot reject loan with status: {loan.status}")
        
        loan.status = 'rejected'
        loan.approved_by = rejected_by  # Use same field for consistency
        loan.rejection_reason = rejection_reason or ''
        loan.save()
        
        return loan
    
    @staticmethod
    def get_loan_summary(loan):
        """
        Get comprehensive loan summary
        
        Args:
            loan: SaccoLoan instance
            
        Returns:
            dict with all loan details
        """
        payments = loan.payments.all()
        guarantors = loan.guarantors.all()
        
        return {
            'loan': {
                'loan_number': loan.loan_number,
                'status': loan.status,
                'member': {
                    'member_number': loan.member.member_number,
                    'name': loan.member.user.get_full_name()
                }
            },
            'amounts': {
                'principal': loan.principal_amount,
                'interest_rate': loan.interest_rate,
                'interest_amount': loan.interest_amount,
                'total_amount': loan.total_amount
            },
            'balances': {
                'principal_paid': loan.amount_paid_principal,
                'interest_paid': loan.amount_paid_interest,
                'principal_balance': loan.balance_principal,
                'interest_balance': loan.balance_interest,
                'total_balance': loan.total_balance
            },
            'dates': {
                'application_date': loan.application_date,
                'approval_date': loan.approval_date,
                'disbursement_date': loan.disbursement_date,
                'due_date': loan.due_date,
                'duration_months': loan.duration_months
            },
            'payments': [
                {
                    'date': p.payment_date,
                    'total': p.total_amount,
                    'principal': p.principal_amount,
                    'interest': p.interest_amount,
                    'method': p.payment_method
                }
                for p in payments
            ],
            'guarantors': [
                {
                    'member_number': g.guarantor.member_number,
                    'name': g.guarantor.user.get_full_name(),
                    'guarantee_amount': g.guarantee_amount
                }
                for g in guarantors
            ],
            'is_overdue': loan.is_overdue
        }
    
    @staticmethod
    @transaction.atomic
    def create_emergency_support(
        sacco,
        member,
        amount,
        reason,
        support_date=None
    ):
        """
        Create emergency support request
        
        Args:
            sacco: SaccoOrganization instance
            member: SaccoMember needing support
            amount: Support amount
            reason: Emergency reason
            support_date: Date of support (defaults to today)
            
        Returns:
            SaccoEmergencySupport instance
        """
        from saccos.models import SaccoEmergencySupport
        
        if not support_date:
            support_date = timezone.now().date()
        
        support = SaccoEmergencySupport.objects.create(
            sacco=sacco,
            member=member,
            support_date=support_date,
            amount=amount,
            reason=reason,
            status='pending'
        )
        
        return support
    
    @staticmethod
    @transaction.atomic
    def approve_emergency_support(support, approved_by):
        """
        Approve and disburse emergency support
        
        Args:
            support: SaccoEmergencySupport instance
            approved_by: User approving the support
            
        Returns:
            dict with support and passbook entry
        """
        from saccos.models import PassbookSection
        from saccos.services.passbook_service import PassbookService
        
        if support.status != 'pending':
            raise ValueError(f"Cannot approve support with status: {support.status}")
        
        support.status = 'disbursed'
        support.approved_by = approved_by
        support.approval_date = timezone.now().date()
        support.save()
        
        # Record in passbook (debit from emergency section)
        try:
            emergency_section = PassbookSection.objects.get(
                sacco=support.sacco,
                section_type='emergency'
            )
            
            passbook = support.member.get_passbook()
            
            entry = PassbookService.record_entry(
                passbook=passbook,
                section=emergency_section,
                amount=support.amount,
                transaction_type='debit',
                description=f'Emergency support - {support.reason[:50]}',
                recorded_by=approved_by,
                transaction_date=support.support_date
            )
            
            support.passbook_entry = entry
            support.save()
            
            return {
                'support': support,
                'passbook_entry': entry
            }
        
        except PassbookSection.DoesNotExist:
            return {
                'support': support,
                'passbook_entry': None,
                'warning': 'No emergency section found in passbook'
            }

    @staticmethod
    @transaction.atomic
    def create_missed_contribution_loan(
        sacco,
        member,
        amount,
        meeting,
        notes='',
        recorded_by=None,
    ):
        """Create zero-interest arrears loan for a missed weekly contribution.

        This reuses the SaccoLoan model with loan_type='missed_contribution' so that
        arrears behave like normal loans in reporting and payments.
        """
        from saccos.models import SaccoLoan
        from django.db.models import Max
        import re

        # Coerce amount to Decimal (may come as string from API)
        amount = Decimal(str(amount))

        # Generate loan number using MAX to avoid UNIQUE constraint issues after deletions
        prefix = sacco.registration_number or 'LOAN'
        last_loan = SaccoLoan.objects.filter(
            sacco=sacco,
            loan_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_loan:
            # Extract the numeric suffix from the last loan number
            match = re.search(r'-(\d+)$', last_loan.loan_number)
            next_num = int(match.group(1)) + 1 if match else 1
        else:
            next_num = 1
        
        loan_number = f"{prefix}-{next_num:05d}"

        today = timezone.now().date()

        # Build human-friendly purpose/title, e.g.:
        # "Cash round 7 - week 4 - 51000"
        if meeting.cash_round:
            round_number = meeting.cash_round.round_number
            purpose = f"Cash round {round_number} - week {meeting.week_number} - {amount}"
        else:
            purpose = f"Missed contribution - week {meeting.week_number} - {amount}"

        base_note = f"Missed weekly contribution during week {meeting.week_number}"
        if notes:
            loan_notes = f"{base_note} - {notes}"
        else:
            loan_notes = base_note

        loan = SaccoLoan.objects.create(
            sacco=sacco,
            member=member,
            loan_number=loan_number,
            principal_amount=amount,
            interest_rate=Decimal('0'),
            interest_amount=Decimal('0'),
            total_amount=amount,
            application_date=today,
            approval_date=today,
            disbursement_date=today,
            due_date=meeting.meeting_date,
            duration_months=0,
            repayment_frequency='weekly',
            amount_paid_principal=Decimal('0'),
            amount_paid_interest=Decimal('0'),
            balance_principal=amount,
            balance_interest=Decimal('0'),
            loan_type='missed_contribution',
            status='disbursed',
            purpose=purpose,
            notes=loan_notes,
            approved_by=recorded_by if recorded_by and getattr(recorded_by, 'id', None) else None,
        )

        return loan
