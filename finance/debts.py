from django.db.models import Sum, DecimalField, Value, Min, Count
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from finance.models import Invoice


class DebtsSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _summary(self, direction: str):
        qs = Invoice.objects.with_paid_and_due().filter(direction=direction)
        unpaid = qs.filter(amount_due__gt=0)
        agg = (
            unpaid
            .values('party_id', 'party__name')
            .annotate(
                invoice_count=Count('id'),
                total_invoiced=Coalesce(Sum('total'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
                total_paid=Coalesce(Sum('paid_amount'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
                total_outstanding=Coalesce(Sum('amount_due'), Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))),
                next_due_date=Min('due_date'),
            )
        )
        return [
            {
                'party_id': r['party_id'],
                'party_name': r['party__name'],
                'invoice_count': r['invoice_count'],
                'total_invoiced': r['total_invoiced'],
                'total_paid': r['total_paid'],
                'total_outstanding': r['total_outstanding'],
                'next_due_date': r['next_due_date'],
            }
            for r in agg
        ]

    @action(detail=False, methods=['get'])
    def debtors(self, request):
        # Debtors = parties owing us = OUTGOING
        return Response(self._summary('outgoing'))

    @action(detail=False, methods=['get'])
    def creditors(self, request):
        # Creditors = parties we owe = INCOMING
        return Response(self._summary('incoming'))
