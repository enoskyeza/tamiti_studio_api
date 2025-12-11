from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as df_filters
from django.db import models as dj_models, transaction as db_transaction
from django.utils import timezone
from django.db.models import Sum, Count, F, DecimalField, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Coalesce
from finance.models import *
from common.enums import InvoiceDirection, FinanceScope, PartyType, PaymentMethod
from finance.services import FinanceService, PersonalFinanceService, LINK_UNSET
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from finance.serializers import *
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Q
from core.api import AppContextLoggingPermission
from django.core.exceptions import ValidationError


class StudioScopedMixin:
    context = "studio"


class BaseModelViewSet(StudioScopedMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, AppContextLoggingPermission]
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
    serializer_class = AccountSerializer
    def get_queryset(self):
        """
        Filter accounts based on scope and user permissions:
        - Personal accounts: only visible to owner
        - Company accounts: visible based on permissions
        - Support scope filtering via query parameter
        """
        # Handle schema generation (swagger_fake_view)
        if getattr(self, 'swagger_fake_view', False):
            return Account.objects.none()
        
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        
        user = self.request.user
        permission_service = PermissionService()
        account_content_type = ContentType.objects.get_for_model(Account)
        
        # Check if scope filtering is requested
        scope_filter = self.request.query_params.get('scope')
        
        # Personal accounts - only show to owner (studio domain only)
        personal_accounts = Account.objects.filter(
            scope=FinanceScope.PERSONAL,
            owner=user,
            domain="studio",
        )
        
        # Company accounts - filter based on permissions (studio domain only)
        company_accounts = Account.objects.filter(
            scope=FinanceScope.COMPANY,
            domain="studio",
        )
        
        # Filter company accounts based on permissions
        accessible_company_accounts = []
        for account in company_accounts:
            if permission_service.has_permission(
                user=user,
                action='read',
                content_type=account_content_type,
                obj=account,
                use_cache=True,
                log_check=False
            ):
                accessible_company_accounts.append(account.id)
        
        # If no specific permissions are set, allow access to all company accounts
        # This maintains backward compatibility
        if not accessible_company_accounts and company_accounts.exists():
            # Check if there are any company account permissions defined
            from permissions.models import Permission
            has_account_permissions = Permission.objects.filter(
                content_type=account_content_type,
                is_active=True
            ).exists()
            
            if not has_account_permissions:
                # No permissions defined, allow all company accounts
                accessible_company_accounts = list(company_accounts.values_list('id', flat=True))
        
        filtered_company_accounts = Account.objects.filter(
            scope=FinanceScope.COMPANY,
            domain="studio",
            id__in=accessible_company_accounts,
        )
        
        # Apply scope filtering if requested
        if scope_filter == 'personal':
            return personal_accounts.order_by('name')
        elif scope_filter == 'company':
            return filtered_company_accounts.order_by('name')
        else:
            # Return both if no scope filter specified (backward compatibility)
            accessible_account_ids = list(personal_accounts.values_list('id', flat=True)) + list(filtered_company_accounts.values_list('id', flat=True))
            return Account.objects.filter(
                id__in=accessible_account_ids,
                domain="studio",
            ).order_by('scope', 'name')


class InvoiceViewSet(BaseModelViewSet):
    queryset = Invoice.objects.all().select_related('party').prefetch_related('items', 'payments')
    filterset_fields = ['direction', 'party', 'issue_date', 'due_date', 'number']
    search_fields = ['number', 'party__name']
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InvoiceCreateUpdateSerializer
        elif self.action == 'retrieve':
            return InvoiceDetailSerializer
        return InvoiceListSerializer

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        invoice = self.get_object()
        s = PaymentCreateSerializer(data=request.data, context={'invoice': invoice, 'request': request})
        s.is_valid(raise_exception=True)
        payment = s.save()

        if not getattr(payment, 'receipt', None):
            Receipt.objects.create(
                number='',
                date=timezone.localdate(),
                party=invoice.party,
                invoice=invoice,
                amount=payment.amount,
                account=payment.account,
                method=payment.method or PaymentMethod.CASH,
                reference='',
                notes=payment.notes or f"Receipt for payment of invoice {invoice.number or f'#{invoice.id}'}",
                payment=payment,
            )

        return Response({'id': payment.pk, 'invoice': invoice.pk, 'amount': str(payment.amount)}, status=201)


class RequisitionViewSet(BaseModelViewSet):
    queryset = Requisition.objects.select_related('requested_by', 'approved_by').prefetch_related('items', 'documents').order_by('-created_at')
    serializer_class = RequisitionSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RequisitionDetailSerializer
        elif self.action in ('create', 'update', 'partial_update'):
            return RequisitionCreateUpdateSerializer
        elif self.action in ('list', 'pending'):
            return RequisitionReadSerializer
        return RequisitionSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        pending = self.queryset.filter(status='pending')
        return Response(self.get_serializer(pending, many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_approve(request.user):
            return Response({'error': 'Permission denied'}, status=403)
        
        requisition.approve(request.user)
        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_approve(request.user):
            return Response({'error': 'Permission denied'}, status=403)

        requisition.reject(request.user)
        return Response({'status': 'rejected'})

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_edit(request.user):
            return Response({'error': 'Permission denied'}, status=403)
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)
        
        from finance.serializers import RequisitionDocumentSerializer
        document = RequisitionDocument.objects.create(
            requisition=requisition,
            file=file_obj,
            filename=file_obj.name,
            file_size=file_obj.size,
            content_type=file_obj.content_type,
            uploaded_by=request.user
        )
        
        serializer = RequisitionDocumentSerializer(document)
        return Response(serializer.data, status=201)
    
    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def delete_document(self, request, pk=None, doc_id=None):
        requisition = self.get_object()
        if not requisition.can_edit(request.user):
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            document = requisition.documents.get(id=doc_id)
            document.delete()
            return Response(status=204)
        except RequisitionDocument.DoesNotExist:
            return Response({'error': 'Document not found'}, status=404)
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        requisition = self.get_object()
        if not requisition.can_edit(request.user):
            return Response({'error': 'Permission denied'}, status=403)
        
        from finance.serializers import RequisitionItemSerializer
        serializer = RequisitionItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(requisition=requisition)
            # Update requisition to use items
            if not requisition.has_items:
                requisition.has_items = True
                requisition.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
    @action(detail=True, methods=['delete'], url_path='items/(?P<item_id>[^/.]+)')
    def delete_item(self, request, pk=None, item_id=None):
        requisition = self.get_object()
        if not requisition.can_edit(request.user):
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            item = requisition.items.get(id=item_id)
            item.delete()
            return Response(status=204)
        except RequisitionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=404)


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

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """Record a payment towards this company goal and update its progress."""
        goal = self.get_object()

        serializer = GoalPaymentCreateSerializer(
            data=request.data,
            context={
                'goal': goal,
                'request': request,
            },
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        goal.refresh_from_db()

        return Response(
            {
                'message': 'Payment recorded successfully',
                'payment_id': payment.id,
                'current': goal.current_amount,
                'target': goal.target_amount,
                'percentage': round((goal.current_amount / goal.target_amount) * 100, 2) if goal.target_amount else 0,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def link_transaction(self, request, pk=None):
        """Link an existing company transaction to this goal.

        If the transaction already has an associated Payment, reuse it and attach
        the goal. If not, create a Payment linked to both the transaction and goal.
        In all cases, enforce that a single transaction can contribute to at most
        one goal at a time.
        """
        goal = self.get_object()
        transaction_id = request.data.get('transaction_id')

        if not transaction_id:
            return Response({"detail": "transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({"detail": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        # Prefer an existing payment linked to this transaction, from either side
        payment = getattr(tx, 'related_payment', None) or getattr(tx, 'linked_payment', None)

        # If there's an existing payment already tied to a different goal, block reuse
        if payment and payment.goal_id and payment.goal_id != goal.id:
            return Response({"detail": "Transaction is already linked to another goal"}, status=status.HTTP_400_BAD_REQUEST)

        if not payment:
            # Create or reuse an internal Party for the goal owner
            owner = goal.owner
            party = Party.objects.filter(user=owner).first()
            if not party:
                name = getattr(owner, 'get_full_name', None)() or getattr(owner, 'username', str(owner.id))
                email = getattr(owner, 'email', '') or ''
                party = Party.objects.create(
                    name=name,
                    email=email,
                    phone='',
                    type=PartyType.INTERNAL,
                    is_internal_user=True,
                    user=owner,
                )

            # Use the transaction amount as the contribution tracked on the goal
            payment = Payment.objects.create(
                direction='incoming',
                amount=tx.amount,
                party=party,
                goal=goal,
                account=tx.account,
                method=PaymentMethod.CASH,
                notes=f"Linked from transaction #{tx.id}",
            )

            # Link both sides for consistency with invoice payment flows
            tx.related_payment = payment
            tx.save(update_fields=['related_payment'])
            payment.transaction = tx
            payment.save(update_fields=['transaction'])
        else:
            # Attach goal to existing payment if not already set
            if payment.goal_id != goal.id:
                payment.goal = goal
                payment.save(update_fields=['goal'])

        # Recalculate goal progress from all incoming payments
        goal.update_progress()
        goal.refresh_from_db()

        return Response({
            "goal_id": goal.id,
            "current": goal.current_amount,
            "target": goal.target_amount,
            "percentage": round((goal.current_amount / goal.target_amount) * 100, 2) if goal.target_amount else 0,
        })


class GoalMilestoneViewSet(BaseModelViewSet):
    queryset = GoalMilestone.objects.select_related('goal')
    serializer_class = GoalMilestoneSerializer


class TransactionViewSet(BaseModelViewSet):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        """
        Filter transactions based on account visibility:
        - Only show transactions for accounts the user has access to
        """
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        
        user = self.request.user
        permission_service = PermissionService()
        account_content_type = ContentType.objects.get_for_model(Account)
        
        # Get accessible accounts (personal + permitted company accounts) in studio domain only
        personal_accounts = Account.objects.filter(
            scope=FinanceScope.PERSONAL,
            owner=user,
            domain="studio",
        )
        
        company_accounts = Account.objects.filter(
            scope=FinanceScope.COMPANY,
            domain="studio",
        )
        accessible_company_accounts = []
        
        for account in company_accounts:
            if permission_service.has_permission(
                user=user,
                action='read',
                content_type=account_content_type,
                obj=account,
                use_cache=True,
                log_check=False
            ):
                accessible_company_accounts.append(account.id)
        
        # Backward compatibility: if no permissions defined, allow all company accounts
        if not accessible_company_accounts and company_accounts.exists():
            from permissions.models import Permission
            has_account_permissions = Permission.objects.filter(
                content_type=account_content_type,
                is_active=True
            ).exists()
            
            if not has_account_permissions:
                accessible_company_accounts = list(company_accounts.values_list('id', flat=True))
        
        # Get all accessible account IDs
        accessible_account_ids = list(personal_accounts.values_list('id', flat=True)) + accessible_company_accounts
        
        # Filter transactions by accessible accounts (studio domain accounts only)
        return Transaction.objects.select_related('account').filter(
            account_id__in=accessible_account_ids
        ).order_by('-date', '-created_at', '-id')


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
    queryset = Quotation.objects.select_related('party').order_by('-created_at', '-id')
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
            existing_payment = Payment.objects.filter(
                invoice=receipt.invoice,
                amount=receipt.amount,
                account=receipt.account,
                receipt__isnull=True,
            ).order_by('id').first()
            if existing_payment:
                receipt.payment = existing_payment
                receipt.save(update_fields=['payment'])
                return

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

    def perform_destroy(self, instance):
        """Delete a receipt and clean up its linked payment and transaction.

        This ensures that removing a receipt also removes the Payment and
        Transaction that were created for it, and that the related Account
        balance and Invoice aggregates reflect the removal.
        """
        payment = instance.payment
        invoice = instance.invoice or (payment.invoice if payment else None)

        # Prefer the Payment.transaction link, but fall back to the reverse
        # relationship in case only one side is populated.
        tx = None
        account = None
        if payment:
            tx = getattr(payment, 'transaction', None) or getattr(payment, 'linked_transaction', None)
            if tx and tx.account_id:
                account = tx.account

        with db_transaction.atomic():
            # Delete the receipt record itself
            instance.delete()

            # Delete the associated transaction and refresh account balance
            if tx:
                tx.delete()
                if account:
                    account.update_balance()

            # Delete the associated payment; invoice aggregates (paid_amount,
            # amount_due) are based on current Payment rows, so they will
            # automatically reflect this removal.
            if payment:
                payment.delete()

            if invoice:
                invoice.refresh_from_db()


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
        # Only include transactions for studio-domain accounts
        income_qs = Transaction.objects.filter(
            type='income',
            account__domain="studio",
        )
        expense_qs = Transaction.objects.filter(
            type='expense',
            account__domain="studio",
        )

        income = income_qs.aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total'] or 0

        # Base expense amounts (excluding charges)
        expense_amount = expense_qs.aggregate(
            total=Coalesce(
                Sum('amount'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total'] or 0

        # Total transaction charges on expense transactions
        expense_charges = expense_qs.aggregate(
            total=Coalesce(
                Sum('transaction_charge'),
                Value(0, output_field=DecimalField(max_digits=12, decimal_places=2)),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )['total'] or 0

        total_expenses = expense_amount + expense_charges

        pending_reqs = Requisition.objects.filter(status='pending').count()

        return Response({
            "total_income": income,
            "total_expenses": total_expenses,
            "total_expenses_excluding_charges": expense_amount,
            "total_transaction_charges": expense_charges,
            "net_balance": income - total_expenses,
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
    filterset_fields = ['type', 'account', 'income_source', 'expense_category', 'date', 'is_recurring', 'linked_invoice', 'linked_goal', 'linked_budget']
    ordering = ['-date']
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_queryset(self):
        return PersonalTransaction.objects.filter(
            user=self.request.user
        ).select_related('account').order_by('-date')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PersonalTransactionDetailSerializer
        elif self.action == 'create':
            return PersonalTransactionCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return PersonalTransactionUpdateSerializer
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
    def link_transaction(self, request, pk=None):
        """Link an existing personal transaction to this savings goal."""
        goal = self.get_object()
        transaction_id = request.data.get('transaction_id')

        if not transaction_id:
            return Response({"detail": "transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tx = PersonalTransaction.objects.get(id=transaction_id, user=request.user)
        except PersonalTransaction.DoesNotExist:
            return Response({"detail": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        if tx.linked_goal and tx.linked_goal_id != goal.id:
            return Response({"detail": "Transaction is already linked to another goal"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            PersonalFinanceService.apply_transaction_linkages(
                tx,
                linked_invoice=LINK_UNSET,
                linked_goal=goal,
                linked_budget=LINK_UNSET,
            )
        except ValidationError as exc:
            detail = getattr(exc, 'message_dict', None) or getattr(exc, 'message', None) or str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        goal.refresh_from_db()
        tx.refresh_from_db()

        return Response({
            'goal_id': goal.id,
            'name': goal.name,
            'target_amount': goal.target_amount,
            'current_amount': goal.current_amount,
            'remaining_amount': goal.remaining_amount,
            'progress_percentage': goal.progress_percentage,
            'is_achieved': goal.is_achieved,
        })

    @action(detail=True, methods=['post'])
    def add_contribution(self, request, pk=None):
        """Add a contribution to the savings goal"""
        goal = self.get_object()
        serializer = PersonalSavingsContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', "Manual contribution")

        try:
            goal.add_contribution(amount, description=description, create_transaction=True)
        except ValidationError as exc:
            # Surface model validation errors (e.g. missing personal account)
            detail = getattr(exc, 'message_dict', None) or getattr(exc, 'message', None) or str(exc)
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        goal.refresh_from_db()

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
        # Split expenses into base amount and transaction charges for clearer reporting
        monthly_expense_amount = sum(
            t.amount for t in transactions_this_month
            if t.type == 'expense'
        )
        monthly_expense_charges = sum(
            t.transaction_charge for t in transactions_this_month
            if t.type == 'expense'
        )
        monthly_expenses = monthly_expense_amount + monthly_expense_charges

        # Operating (P&L) view: only transactions that affect profit
        operating_income = sum(
            t.amount for t in transactions_this_month
            if t.type == 'income' and getattr(t, 'affects_profit', True)
        )
        operating_expenses = sum(
            t.amount + t.transaction_charge for t in transactions_this_month
            if t.type == 'expense' and getattr(t, 'affects_profit', True)
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
            'operating_income': operating_income,
            'operating_expenses': operating_expenses,
            'operating_net': operating_income - operating_expenses,
            'monthly_expenses_excluding_charges': monthly_expense_amount,
            'monthly_transaction_charges': monthly_expense_charges,
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


class InterestSummaryAPIView(APIView):
    """Expose aggregated interest paid and received for personal finance"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from finance.services import PersonalFinanceService

        start_param = request.query_params.get('start_date')
        end_param = request.query_params.get('end_date')
        start_date = end_date = None

        try:
            if start_param:
                start_date = datetime.strptime(start_param, '%Y-%m-%d').date()
            if end_param:
                end_date = datetime.strptime(end_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Dates must be provided in YYYY-MM-DD format.'}, status=status.HTTP_400_BAD_REQUEST)

        if start_date and end_date and start_date > end_date:
            return Response({'detail': 'start_date cannot be after end_date.'}, status=status.HTTP_400_BAD_REQUEST)

        summary = PersonalFinanceService.get_interest_summary(request.user, start_date, end_date)
        serializer = InterestSummarySerializer(summary)
        return Response(serializer.data)


# COMPANY FINANCE VIEWSETS

class CompanyBudgetViewSet(BaseModelViewSet):
    """ViewSet for company budgets"""
    serializer_class = CompanyBudgetListSerializer
    search_fields = ['name', 'department__name', 'category']
    filterset_fields = ['department', 'category', 'period', 'is_active']
    ordering = ['-start_date', 'name']
    
    def get_queryset(self):
        """Filter budgets based on user permissions"""
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        
        user = self.request.user
        permission_service = PermissionService()
        budget_content_type = ContentType.objects.get_for_model(CompanyBudget)
        
        # Get all company budgets
        all_budgets = CompanyBudget.objects.all()
        
        # Filter based on permissions
        accessible_budgets = []
        for budget in all_budgets:
            if permission_service.has_permission(
                user=user,
                action='read',
                content_type=budget_content_type,
                obj=budget,
                use_cache=True,
                log_check=False
            ):
                accessible_budgets.append(budget.id)
        
        # If no specific permissions, allow access to all (backward compatibility)
        if not accessible_budgets and all_budgets.exists():
            accessible_budgets = list(all_budgets.values_list('id', flat=True))
        
        return CompanyBudget.objects.filter(id__in=accessible_budgets).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyBudgetCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return CompanyBudgetUpdateSerializer
        return CompanyBudgetListSerializer

    def perform_create(self, serializer):
        """Set approval fields if user has permission"""
        if self.request.user.is_staff:
            serializer.save(
                approved_by=self.request.user,
                approved_at=timezone.now()
            )
        else:
            serializer.save()


class CompanySavingsGoalViewSet(BaseModelViewSet):
    """ViewSet for company savings goals"""
    serializer_class = CompanySavingsGoalListSerializer
    search_fields = ['name', 'description', 'department__name']
    filterset_fields = ['department', 'priority', 'is_active']
    ordering = ['-priority', '-target_date']
    
    def get_queryset(self):
        """Filter savings goals based on user permissions"""
        # Handle schema generation (swagger_fake_view)
        if getattr(self, 'swagger_fake_view', False):
            return CompanySavingsGoal.objects.none()
        
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        
        user = self.request.user
        permission_service = PermissionService()
        goal_content_type = ContentType.objects.get_for_model(CompanySavingsGoal)
        
        # Get all company savings goals
        all_goals = CompanySavingsGoal.objects.all()
        
        # Filter based on permissions
        accessible_goals = []
        for goal in all_goals:
            if permission_service.has_permission(
                user=user,
                action='read',
                content_type=goal_content_type,
                obj=goal,
                use_cache=True,
                log_check=False
            ):
                accessible_goals.append(goal.id)
        
        # If no specific permissions, allow access to all (backward compatibility)
        if not accessible_goals and all_goals.exists():
            accessible_goals = list(all_goals.values_list('id', flat=True))
        
        return CompanySavingsGoal.objects.filter(id__in=accessible_goals).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CompanySavingsGoalCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return CompanySavingsGoalUpdateSerializer
        return CompanySavingsGoalListSerializer

    @action(detail=True, methods=['post'])
    def add_contribution(self, request, pk=None):
        """Add a contribution to the savings goal"""
        goal = self.get_object()
        amount = request.data.get('amount')
        
        if not amount or float(amount) <= 0:
            return Response(
                {'error': 'Valid amount is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        goal.current_amount += Decimal(str(amount))
        goal.save(update_fields=['current_amount'])
        
        serializer = self.get_serializer(goal)
        return Response(serializer.data)


class CompanyRecurringTransactionViewSet(BaseModelViewSet):
    """ViewSet for company recurring transactions"""
    serializer_class = CompanyRecurringTransactionListSerializer
    search_fields = ['name', 'department__name', 'account__name']
    filterset_fields = ['department', 'transaction_type', 'category', 'frequency', 'is_active', 'requires_approval']
    ordering = ['next_due_date', 'name']
    
    def get_queryset(self):
        """Filter recurring transactions based on user permissions"""
        from permissions.services import PermissionService
        from django.contrib.contenttypes.models import ContentType
        
        user = self.request.user
        permission_service = PermissionService()
        transaction_content_type = ContentType.objects.get_for_model(CompanyRecurringTransaction)
        
        # Get all company recurring transactions
        all_transactions = CompanyRecurringTransaction.objects.all()
        
        # Filter based on permissions
        accessible_transactions = []
        for transaction in all_transactions:
            if permission_service.has_permission(
                user=user,
                action='read',
                content_type=transaction_content_type,
                obj=transaction,
                use_cache=True,
                log_check=False
            ):
                accessible_transactions.append(transaction.id)
        
        # If no specific permissions, allow access to all (backward compatibility)
        if not accessible_transactions and all_transactions.exists():
            accessible_transactions = list(all_transactions.values_list('id', flat=True))
        
        return CompanyRecurringTransaction.objects.filter(id__in=accessible_transactions).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyRecurringTransactionCreateSerializer
        elif self.action in ('update', 'partial_update'):
            return CompanyRecurringTransactionUpdateSerializer
        return CompanyRecurringTransactionListSerializer

    def perform_create(self, serializer):
        """Set approval fields if user has permission"""
        if self.request.user.is_staff:
            serializer.save(approved_by=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def create_transaction(self, request, pk=None):
        """Manually create a transaction from this recurring template"""
        recurring_transaction = self.get_object()
        
        try:
            transaction = recurring_transaction.create_transaction()
            return Response({
                'message': 'Transaction created successfully',
                'transaction_id': transaction.id,
                'next_due_date': recurring_transaction.next_due_date
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def due_transactions(self, request):
        """Get all due recurring transactions"""
        due_transactions = self.get_queryset().filter(
            is_active=True,
            next_due_date__lte=timezone.now().date()
        )
        serializer = self.get_serializer(due_transactions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue_transactions(self, request):
        """Get all overdue recurring transactions"""
        overdue_transactions = self.get_queryset().filter(
            is_active=True,
            next_due_date__lt=timezone.now().date()
        )
        serializer = self.get_serializer(overdue_transactions, many=True)
        return Response(serializer.data)
