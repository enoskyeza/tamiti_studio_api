from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from django.db import models as dj_models
from django.utils import timezone
from django.db.models import Sum, Count, F, DecimalField, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Coalesce
from finance.models import *
from common.enums import InvoiceDirection, FinanceScope
from finance.services import FinanceService
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from finance.serializers import *
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Q


class BaseModelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = '__all__'
    # Do not set a global search_fields; define per-view to avoid DRF errors
    search_fields = []

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
    queryset = Invoice.objects.all().select_related('party')
    filterset_fields = ['direction', 'party', 'issue_date', 'due_date', 'number']
    search_fields = ['number', 'party__name']
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InvoiceCreateUpdateSerializer
        return InvoiceListSerializer

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        invoice = self.get_object()
        s = PaymentCreateSerializer(data=request.data, context={'invoice': invoice, 'request': request})
        s.is_valid(raise_exception=True)
        payment = s.save()
        return Response({'id': payment.pk, 'invoice': invoice.pk, 'amount': str(payment.amount)}, status=201)


class RequisitionViewSet(BaseModelViewSet):
    queryset = Requisition.objects.select_related('requested_by', 'approved_by').all()
    serializer_class = RequisitionSerializer

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve', 'pending'):
            return RequisitionReadSerializer
        return RequisitionSerializer

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


class GoalMilestoneViewSet(BaseModelViewSet):
    queryset = GoalMilestone.objects.select_related('goal')
    serializer_class = GoalMilestoneSerializer


class TransactionViewSet(BaseModelViewSet):
    queryset = Transaction.objects.select_related('account')
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.order_by('-date')


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Payment.objects.select_related('invoice', 'account', 'transaction')
    serializer_class = PaymentSerializer

    @action(detail=False, methods=['get'])
    def by_goal(self, request):
        goal_id = request.query_params.get('goal')
        if goal_id:
            payments = self.queryset.filter(goal_id=goal_id)
            return Response(self.get_serializer(payments, many=True).data)
        return Response({"detail": "Missing goal param"}, status=status.HTTP_400_BAD_REQUEST)


class QuotationViewSet(BaseModelViewSet):
    queryset = Quotation.objects.select_related('party')
    serializer_class = QuotationSerializer

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        quote = self.get_object()
        if quote.status == 'accepted':
            return Response({"detail": "Quotation already accepted"}, status=status.HTTP_400_BAD_REQUEST)
        quote.status = 'accepted'
        quote.save(update_fields=['status'])
        return Response({"status": "accepted", "quotation_id": quote.id})

    @action(detail=True, methods=['post'], url_path='create-invoice')
    def create_invoice(self, request, pk=None):
        """Optionally convert an accepted quotation into an OUTGOING invoice."""
        quote = self.get_object()
        if quote.status != 'accepted':
            return Response({"detail": "Quotation must be accepted before creating an invoice."}, status=status.HTTP_400_BAD_REQUEST)
        due_date = request.data.get('due_date') or timezone.now().date()
        invoice = Invoice.objects.create(
            party=quote.party,
            direction=InvoiceDirection.OUTGOING,
            total=quote.total_amount,
            issue_date=timezone.now().date(),
            due_date=due_date,
        )
        return Response({'invoice_id': invoice.id, 'invoice_total': str(invoice.total)}, status=status.HTTP_201_CREATED)


class ReceiptViewSet(BaseModelViewSet):
    queryset = Receipt.objects.select_related('party', 'invoice', 'account', 'payment')
    serializer_class = ReceiptSerializer

    def perform_create(self, serializer):
        receipt = serializer.save()
        # If linked to an invoice, record payment via FinanceService (ensures Transaction is created)
        if receipt.invoice and not receipt.payment:
            payment = FinanceService.record_invoice_payment(
                invoice=receipt.invoice,
                amount=receipt.amount,
                account=receipt.account,
                method=receipt.method,
                notes=receipt.notes,
                created_by=getattr(self.request, 'user', None),
            )
            receipt.payment = payment
            receipt.save(update_fields=['payment'])


class InvoiceItemViewSet(BaseModelViewSet):
    queryset = InvoiceItem.objects.select_related('invoice')
    serializer_class = InvoiceItemSerializer


class QuotationItemViewSet(BaseModelViewSet):
    queryset = QuotationItem.objects.select_related('quotation')
    serializer_class = QuotationItemSerializer


class ReceiptItemViewSet(BaseModelViewSet):
    queryset = ReceiptItem.objects.select_related('receipt')
    serializer_class = ReceiptItemSerializer


class DebtsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def _aggregate_by_party(self, direction: str):
        # Summarize unpaid invoices by party for the given direction
        base_qs = Invoice.objects.unpaid().filter(direction=direction)
        aggregated = (
            base_qs
            .values('party', 'party__name', 'party__email', 'party__phone')
            .annotate(
                invoice_count=Count('id', distinct=True),
                total_invoiced=Coalesce(
                    Sum('total'),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                total_paid=Coalesce(
                    Sum('payments__amount'),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
            )
        )
        # Calculate outstanding = total_invoiced - total_paid on the fly
        results = []
        for row in aggregated:
            outstanding = row['total_invoiced'] - row['total_paid']
            if outstanding <= 0:
                continue
            results.append({
                'party_id': row['party'],
                'party_name': row['party__name'],
                'party_email': row['party__email'],
                'party_phone': row['party__phone'],
                'invoice_count': row['invoice_count'],
                'total_invoiced': row['total_invoiced'],
                'total_paid': row['total_paid'],
                'total_outstanding': outstanding,
            })
        return results

    @action(detail=False, methods=['get'])
    def debtors(self, request):
        """Parties owing us (AR): direction='outgoing', unpaid."""
        data = self._aggregate_by_party(direction='outgoing')
        serializer = PartyDebtSummarySerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def creditors(self, request):
        """Parties we owe (AP): direction='incoming', unpaid."""
        data = self._aggregate_by_party(direction='incoming')
        serializer = PartyDebtSummarySerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'party/(?P<party_id>[^/.]+)')
    def party(self, request, party_id=None):
        """Detail for a party's debts/credits; query param 'direction' required (incoming|outgoing)."""
        direction = request.query_params.get('direction')
        if direction not in ('incoming', 'outgoing'):
            return Response({"detail": "Missing or invalid 'direction' (incoming|outgoing)"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            party = Party.objects.get(id=party_id)
        except Party.DoesNotExist:
            return Response({"detail": "Party not found"}, status=status.HTTP_404_NOT_FOUND)

        invoices_qs = (
            Invoice.objects
            .filter(party=party, direction=direction)
            .prefetch_related('payments')
            .order_by('-issue_date')
        )
        invoices = [inv for inv in invoices_qs if inv.amount_due > 0]
        outstanding_total = sum((inv.amount_due for inv in invoices), start=Decimal('0'))

        # Payments for these invoices
        payments = Payment.objects.filter(invoice__in=invoices).order_by('-created_at')
        # Transactions linked to those payments or invoices
        transactions = Transaction.objects.filter(
            dj_models.Q(related_invoice__in=invoices) | dj_models.Q(related_payment__in=payments)
        ).order_by('-date')

        payload = {
            'party': party,
            'direction': direction,
            'outstanding_total': outstanding_total,
            # Pass model instances; PartyDebtDetailSerializer handles nested serialization
            'invoices': invoices,
            'payments': payments,
            'transactions': transactions,
        }

        return Response(PartyDebtDetailSerializer(payload).data)


class FinanceSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        income = Transaction.objects.filter(type='income').aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total'] or 0

        expenses = Transaction.objects.filter(type='expense').aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total'] or 0

        pending_reqs = Requisition.objects.filter(status='pending').count()

        return Response({
            "total_income": income,
            "total_expenses": expenses,
            "net_balance": income - expenses,
            "pending_requisitions": pending_reqs,
        })


# PERSONAL FINANCE VIEWSETS

class PersonalAccountViewSet(BaseModelViewSet):
    """ViewSet for personal accounts - filtered by user ownership"""
    serializer_class = PersonalAccountListSerializer
    search_fields = ['name', 'number']
    filterset_fields = ['type', 'currency', 'is_active']
    
    def get_queryset(self):
        return Account.objects.filter(
            scope=FinanceScope.PERSONAL,
            owner=self.request.user
        ).order_by('name')
    
    def get_serializer_class(self):
        if self.action in ('create',):
            return PersonalAccountCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return PersonalAccountUpdateSerializer
        return PersonalAccountListSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, scope=FinanceScope.PERSONAL)


class PersonalTransactionViewSet(BaseModelViewSet):
    """ViewSet for personal transactions with analytics actions"""
    serializer_class = PersonalTransactionListSerializer
    search_fields = ['description', 'reason', 'reference_number', 'location']
    filterset_fields = ['type', 'account', 'income_source', 'expense_category', 'date', 'is_recurring']
    ordering = ['-date']
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_queryset(self):
        return PersonalTransaction.objects.filter(
            user=self.request.user
        ).select_related('account').order_by('-date')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PersonalTransactionDetailSerializer
        elif self.action in ('create', 'update', 'partial_update'):
            return PersonalTransactionCreateSerializer
        return PersonalTransactionListSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        """Get monthly income/expense summary"""
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))

        start_date = timezone.datetime(year, month, 1).date()
        if month == 12:
            end_date = timezone.datetime(year + 1, 1, 1).date()
        else:
            end_date = timezone.datetime(year, month + 1, 1).date()

        transactions = self.get_queryset().filter(
            date__gte=start_date,
            date__lt=end_date
        )

        summary_data = {
            'year': year,
            'month': month,
            'transactions': transactions
        }

        serializer = PersonalMonthlySummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def spending_insights(self, request):
        """Get spending insights and analytics"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        transactions = self.get_queryset().filter(date__gte=start_date)

        insights_data = {
            'period_days': days,
            'start_date': start_date,
            'end_date': timezone.now().date(),
            'transactions': transactions
        }

        serializer = PersonalSpendingInsightsSerializer(insights_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def category_breakdown(self, request):
        """Get expense breakdown by category"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        expenses = self.get_queryset().filter(
            type='expense',
            date__gte=start_date
        )

        breakdown_data = {
            'period_days': days,
            'start_date': start_date,
            'end_date': timezone.now().date(),
            'expenses': expenses
        }

        serializer = PersonalCategoryBreakdownSerializer(breakdown_data)
        return Response(serializer.data)


class PersonalBudgetViewSet(BaseModelViewSet):
    """ViewSet for personal budgets with progress tracking"""
    serializer_class = PersonalBudgetListSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'period', 'is_active']
    
    def get_queryset(self):
        return PersonalBudget.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalBudgetCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return PersonalBudgetUpdateSerializer
        return PersonalBudgetListSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get budget progress and remaining amount"""
        budget = self.get_object()
        return Response({
            'budget_id': budget.id,
            'name': budget.name,
            'allocated_amount': budget.allocated_amount,
            'spent_amount': budget.spent_amount,
            'remaining_amount': budget.remaining_amount,
            'progress_percentage': budget.progress_percentage,
            'is_exceeded': budget.is_exceeded,
            'period': budget.period,
            'start_date': budget.start_date,
            'end_date': budget.end_date,
        })

    @action(detail=False, methods=['get'])
    def current_budgets(self, request):
        """Get all active budgets for current period"""
        current_budgets = self.get_queryset().filter(
            is_active=True,
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        serializer = self.get_serializer(current_budgets, many=True)
        return Response(serializer.data)


class PersonalSavingsGoalViewSet(BaseModelViewSet):
    """ViewSet for personal savings goals with progress tracking"""
    serializer_class = PersonalSavingsGoalListSerializer
    search_fields = ['title', 'description']
    filterset_fields = ['is_achieved', 'target_date']
    
    def get_queryset(self):
        return PersonalSavingsGoal.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalSavingsGoalCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return PersonalSavingsGoalUpdateSerializer
        return PersonalSavingsGoalListSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get savings goal progress"""
        goal = self.get_object()
        return Response({
            'goal_id': goal.id,
            'name': goal.name,
            'target_amount': goal.target_amount,
            'current_amount': goal.current_amount,
            'remaining_amount': goal.remaining_amount,
            'progress_percentage': goal.progress_percentage,
            'is_achieved': goal.is_achieved,
            'target_date': goal.target_date,
            'days_remaining': (goal.target_date - timezone.now().date()).days if goal.target_date else None,
        })

    @action(detail=True, methods=['post'])
    def add_contribution(self, request, pk=None):
        """Add a contribution to the savings goal"""
        goal = self.get_object()
        amount = request.data.get('amount')

        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                return Response(
                    {'error': 'Amount must be positive'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        goal.current_amount += amount
        goal.save(update_fields=['current_amount'])

        return Response({
            'message': 'Contribution added successfully',
            'new_current_amount': goal.current_amount,
            'progress_percentage': goal.progress_percentage,
            'is_achieved': goal.is_achieved,
        })


class PersonalTransactionRecurringViewSet(BaseModelViewSet):
    """ViewSet for recurring personal transactions"""
    serializer_class = PersonalTransactionRecurringListSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['frequency', 'is_active', 'type']
    
    def get_queryset(self):
        return PersonalTransactionRecurring.objects.filter(
            user=self.request.user
        ).select_related('account').order_by('name')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalTransactionRecurringCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return PersonalTransactionRecurringUpdateSerializer
        return PersonalTransactionRecurringListSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def execute_now(self, request, pk=None):
        """Manually execute a recurring transaction"""
        recurring = self.get_object()

        if not recurring.is_active:
            return Response(
                {'error': 'Cannot execute inactive recurring transaction'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the actual transaction
        transaction = PersonalTransaction.objects.create(
            user=recurring.user,
            type=recurring.type,
            amount=recurring.amount,
            account=recurring.account,
            description=recurring.description,
            transaction_charge=recurring.transaction_charge,
            income_source=recurring.income_source if recurring.type == 'income' else '',
            expense_category=recurring.expense_category if recurring.type == 'expense' else '',
            reason=recurring.reason,
            is_recurring=True,
            recurring_parent=None,  # This is the parent
        )

        # Update next due date
        recurring.update_next_execution()
        
        return Response({
            'message': 'Recurring transaction executed successfully',
            'transaction_id': transaction.id,
            'next_due_date': recurring.next_due_date,
        })

    @action(detail=False, methods=['get'])
    def due_today(self, request):
        """Get recurring transactions due today"""
        today = timezone.now().date()
        due_transactions = self.get_queryset().filter(
            is_active=True,
            next_due_date__lte=today
        )
        serializer = self.get_serializer(due_transactions, many=True)
        return Response(serializer.data)


class PersonalFinanceDashboardView(APIView):
    """Dashboard view for personal finance overview"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get user's personal accounts
        accounts = Account.objects.filter(
            scope=FinanceScope.PERSONAL,
            owner=user,
            is_active=True
        )

        # Calculate total balance
        total_balance = sum(account.balance for account in accounts)

        # Get current month transactions
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        transactions_this_month = PersonalTransaction.objects.filter(
            user=user,
            date__gte=start_of_month
        )

        # Calculate monthly income and expenses
        monthly_income = sum(
            t.amount for t in transactions_this_month
            if t.type == 'income'
        )
        monthly_expenses = sum(
            t.amount + t.transaction_charge for t in transactions_this_month
            if t.type == 'expense'
        )

        # Get active budgets
        active_budgets = PersonalBudget.objects.filter(
            user=user,
            is_active=True,
            start_date__lte=now.date(),
            end_date__gte=now.date()
        ).count()

        # Get savings goals
        savings_goals = PersonalSavingsGoal.objects.filter(
            user=user,
            is_achieved=False
        ).count()

        # Get due recurring transactions
        due_recurring = PersonalTransactionRecurring.objects.filter(
            user=user,
            is_active=True,
            next_due_date__lte=now.date()
        ).count()

        return Response({
            'total_balance': total_balance,
            'accounts_count': accounts.count(),
            'monthly_income': monthly_income,
            'monthly_expenses': monthly_expenses,
            'net_monthly': monthly_income - monthly_expenses,
            'active_budgets': active_budgets,
            'active_savings_goals': savings_goals,
            'due_recurring_transactions': due_recurring,
            'transactions_this_month': transactions_this_month.count(),
        })


# INVOICE, DEBT AND CREDIT MANAGEMENT
class PartyFinanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/finance/party-finance/?role=debtors | creditors
    Returns parties with unpaid invoices (nested) + total_due per party.
    """
    serializer_class = PartyWithUnpaidSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        role = (self.request.query_params.get('role') or 'debtors').lower()
        direction = InvoiceDirection.OUTGOING if role == 'debtors' else InvoiceDirection.INCOMING

        # Unpaid invoices for SQL-only subquery usage (safe to use unpaid())
        inv_unpaid_sub = Invoice.objects.unpaid().filter(direction=direction)
        # Prefetch queryset: avoid unpaid() to prevent 'amount_due' annotation conflicting with @property
        inv_prefetch = (
            Invoice.objects.filter(direction=direction)
            .annotate(
                _paid=Coalesce(
                    Sum('payments__amount'),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .annotate(_due=F('total') - F('_paid'))
            .filter(_due__gt=0)
            .order_by('-issue_date')
        )

        per_party_total_due = (
            inv_unpaid_sub.filter(party=OuterRef('pk'))
            .values('party')
            .annotate(
                total_invoiced=Coalesce(
                    Sum('total'),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                total_paid=Coalesce(
                    Sum('payments__amount'),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .annotate(td=F('total_invoiced') - F('total_paid'))
            .values('td')[:1]
        )

        qs = (
            Party.objects
            .filter(invoices__in=inv_prefetch)
            .distinct()
            .annotate(
                total_due=Coalesce(
                    Subquery(per_party_total_due, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                )
            )
            .prefetch_related(
                Prefetch('invoices', queryset=inv_prefetch, to_attr='unpaid_invoices')
            )
        )
        return qs


# Account Transfer ViewSets
class PersonalAccountTransferViewSet(viewsets.ModelViewSet):
    """ViewSet for managing account transfers"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-date']
    
    def get_queryset(self):
        return PersonalAccountTransfer.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalAccountTransferCreateSerializer
        return PersonalAccountTransferListSerializer


# Debt Management ViewSets
class PersonalDebtViewSet(viewsets.ModelViewSet):
    """ViewSet for managing personal debts"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering = ['due_date', '-created_at']
    search_fields = ['creditor_name', 'description']
    
    def get_queryset(self):
        return PersonalDebt.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalDebtCreateSerializer
        return PersonalDebtListSerializer
    
    @action(detail=True, methods=['post'])
    def make_payment(self, request, pk=None):
        """Make a payment towards this debt"""
        debt = self.get_object()
        serializer = DebtPaymentCreateSerializer(
            data=request.data,
            context={'request': request, 'debt_id': debt.id}
        )
        if serializer.is_valid():
            payment = serializer.save()
            return Response(
                DebtPaymentListSerializer(payment).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """Get all payments for this debt"""
        debt = self.get_object()
        payments = debt.payments.all().order_by('-payment_date')
        serializer = DebtPaymentListSerializer(payments, many=True)
        return Response(serializer.data)


class PersonalLoanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing personal loans"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering = ['due_date', '-created_at']
    search_fields = ['borrower_name', 'description']
    
    def get_queryset(self):
        return PersonalLoan.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PersonalLoanCreateSerializer
        return PersonalLoanListSerializer
    
    @action(detail=True, methods=['post'])
    def receive_repayment(self, request, pk=None):
        """Receive a repayment for this loan"""
        loan = self.get_object()
        serializer = LoanRepaymentCreateSerializer(
            data=request.data,
            context={'request': request, 'loan_id': loan.id}
        )
        if serializer.is_valid():
            repayment = serializer.save()
            return Response(
                LoanRepaymentListSerializer(repayment).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def repayments(self, request, pk=None):
        """Get all repayments for this loan"""
        loan = self.get_object()
        repayments = loan.repayments.all().order_by('-repayment_date')
        serializer = LoanRepaymentListSerializer(repayments, many=True)
        return Response(serializer.data)


class DebtPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing debt payments"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DebtPaymentListSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-payment_date']
    
    def get_queryset(self):
        return DebtPayment.objects.filter(debt__user=self.request.user)


class LoanRepaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing loan repayments"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LoanRepaymentListSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-repayment_date']
    
    def get_queryset(self):
        return LoanRepayment.objects.filter(loan__user=self.request.user)


class DebtSummaryAPIView(APIView):
    """API view for debt and loan summary"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from finance.services import PersonalFinanceService
        summary = PersonalFinanceService.get_debt_summary(request.user)
        serializer = DebtSummarySerializer(summary)
        return Response(serializer.data)
