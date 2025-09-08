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
from common.enums import InvoiceDirection
from finance.services import FinanceService
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from finance.serializers import *
from decimal import Decimal


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
