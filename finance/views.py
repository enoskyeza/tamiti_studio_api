from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from django.db import models as dj_models
from django.utils import timezone
from django.db.models import Sum, Count, F, DecimalField, Value
from django.db.models.functions import Coalesce
from finance.models import *
from finance.serializers import *
from decimal import Decimal


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


class GoalMilestoneViewSet(BaseModelViewSet):
    queryset = GoalMilestone.objects.select_related('goal')
    serializer_class = GoalMilestoneSerializer


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


class QuotationViewSet(BaseModelViewSet):
    queryset = Quotation.objects.select_related('party')
    serializer_class = QuotationSerializer

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        quote = self.get_object()
        if quote.status == 'accepted':
            return Response({"detail": "Quotation already accepted"}, status=status.HTTP_400_BAD_REQUEST)

        due_date = request.data.get('due_date') or (timezone.now().date())
        invoice = Invoice.objects.create(
            party=quote.party,
            direction='incoming',
            total_amount=quote.total_amount,
            description=quote.description,
            issued_date=timezone.now().date(),
            due_date=due_date,
            is_paid=False,
        )
        quote.status = 'accepted'
        quote.save(update_fields=['status'])
        return Response({
            'invoice_id': invoice.id,
            'invoice_total': str(invoice.total_amount),
        }, status=status.HTTP_201_CREATED)


class ReceiptViewSet(BaseModelViewSet):
    queryset = Receipt.objects.select_related('party', 'invoice', 'account', 'payment')
    serializer_class = ReceiptSerializer

    def perform_create(self, serializer):
        receipt = serializer.save()
        # If no payment linked, create one for consistency and accounting
        if not receipt.payment:
            payment = Payment.objects.create(
                direction='incoming',
                amount=receipt.amount,
                party=receipt.party,
                invoice=receipt.invoice,
                account=receipt.account,
                notes=receipt.notes,
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
    permission_classes = [permissions.IsAuthenticated]

    def _aggregate_by_party(self, direction: str):
        # Summarize unpaid invoices by party for the given direction
        base_qs = Invoice.objects.filter(direction=direction, is_paid=False)
        aggregated = (
            base_qs
            .values('party', 'party__name')
            .annotate(
                invoice_count=Count('id', distinct=True),
                total_invoiced=Coalesce(
                    Sum('total_amount'),
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
                'invoice_count': row['invoice_count'],
                'total_invoiced': row['total_invoiced'],
                'total_paid': row['total_paid'],
                'total_outstanding': outstanding,
            })
        return results

    @action(detail=False, methods=['get'])
    def debtors(self, request):
        """Parties owing us (AR): direction='incoming', unpaid."""
        data = self._aggregate_by_party(direction='incoming')
        serializer = PartyDebtSummarySerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def creditors(self, request):
        """Parties owing us (AR): direction='incoming', unpaid."""
        data = self._aggregate_by_party(direction='outgoing')
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

        invoices = (
            Invoice.objects
            .filter(party=party, direction=direction)
            .prefetch_related('payments')
            .order_by('-issued_date')
        )
        # Outstanding total across unpaid invoices
        outstanding_total = sum((inv.balance for inv in invoices if not inv.is_paid), start=Decimal('0'))

        # Payments for these invoices
        payments = Payment.objects.filter(invoice__in=invoices).order_by('-created_at')
        # Transactions linked to those payments or invoices
        transactions = Transaction.objects.filter(
            dj_models.Q(related_invoice__in=invoices) | dj_models.Q(related_payment__in=payments)
        ).order_by('-date')

        payload = {
            'party': PartySerializer(party).data,
            'direction': direction,
            'outstanding_total': outstanding_total,
            'invoices': InvoiceBriefSerializer(invoices, many=True).data,
            'payments': PaymentBriefSerializer(payments, many=True).data,
            'transactions': TransactionBriefSerializer(transactions, many=True).data,
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

    def get_queryset(self):
        role = (self.request.query_params.get('role') or 'debtors').lower()
        direction = InvoiceDirection.OUTGOING if role == 'debtors' else InvoiceDirection.INCOMING

        inv_unpaid = Invoice.objects.unpaid().filter(direction=direction)

        # total_due per party via Subquery (fast & precise)
        per_party_total_due = (
            inv_unpaid.filter(party=OuterRef('pk'))
            .values('party')
            .annotate(td=Sum('amount_due'))
            .values('td')[:1]
        )

        qs = (Party.objects
              .filter(invoices__in=inv_unpaid)
              .distinct()
              .annotate(
                  total_due=Coalesce(
                      Subquery(per_party_total_due, output_field=DecimalField(max_digits=12, decimal_places=2)),
                      V(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                  )
              )
              .prefetch_related(
                  Prefetch('invoices', queryset=inv_unpaid.order_by('-issue_date'), to_attr='unpaid_invoices')
              ))
        return qs


class InvoiceViewSet(BaseModelViewSet):
    queryset = Invoice.objects.all()
    filterset_fields = ['direction', 'party', 'issue_date', 'due_date']
    search_fields = ['number', 'party__name']

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
