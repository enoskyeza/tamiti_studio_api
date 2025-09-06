from rest_framework import serializers
from finance.models import (
    Party, Account, Invoice, Payment, Transaction,
    Goal, GoalMilestone, Requisition, Quotation, Receipt,
    InvoiceItem, QuotationItem, ReceiptItem
)
from common.enums import PartyType
from finance.services import FinanceService


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = '__all__'


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'


class PartyInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = ('id', 'name', 'email', 'phone', 'type', 'is_internal_user')


class InvoiceSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    items = serializers.SerializerMethodField()
    # Accept either a party id or a nested party object for creation
    party = serializers.JSONField()

    class Meta:
        model = Invoice
        fields = '__all__'

    def get_items(self, obj):
        return InvoiceItemSerializer(obj.items.all(), many=True).data

    def _resolve_party(self, party_data):
        # Accepts int id or dict with fields for new/existing party
        if isinstance(party_data, int):
            return Party.objects.get(pk=party_data)
        if isinstance(party_data, dict):
            pid = party_data.get('id')
            if pid:
                return Party.objects.get(pk=pid)
            # create new party
            p = Party.objects.create(
                name=party_data.get('name', ''),
                email=party_data.get('email') or None,
                phone=party_data.get('phone') or '',
                type=party_data.get('type') or PartyType.CLIENT,
                is_internal_user=party_data.get('is_internal_user') or False,
            )
            return p
        raise serializers.ValidationError({'party': 'Invalid party payload'})

    def create(self, validated_data):
        party_payload = self.initial_data.get('party')
        if party_payload is not None:
            party = self._resolve_party(party_payload)
            validated_data['party'] = party
        return super().create(validated_data)

    def update(self, instance, validated_data):
        party_payload = self.initial_data.get('party')
        if party_payload is not None and isinstance(party_payload, (dict, int)):
            party = self._resolve_party(party_payload)
            validated_data['party'] = party
        return super().update(instance, validated_data)


class GoalMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalMilestone
        fields = '__all__'


class GoalSerializer(serializers.ModelSerializer):
    milestones = GoalMilestoneSerializer(many=True, read_only=True)

    class Meta:
        model = Goal
        fields = '__all__'


# --- Brief serializers for debts/creditors views ---
class InvoiceBriefSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'party', 'party_name', 'direction', 'total_amount', 'issued_date',
            'due_date', 'is_paid', 'balance'
        )


class PaymentBriefSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'direction', 'amount', 'party', 'party_name', 'invoice', 'account',
            'notes', 'created_at'
        )


class TransactionBriefSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'type', 'amount', 'description', 'account', 'account_name', 'category',
            'related_invoice', 'related_requisition', 'related_payment', 'date'
        )


class PartyDebtSummarySerializer(serializers.Serializer):
    party_id = serializers.IntegerField()
    party_name = serializers.CharField()
    invoice_count = serializers.IntegerField()
    total_invoiced = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)


class PartyDebtDetailSerializer(serializers.Serializer):
    party = PartySerializer()
    direction = serializers.ChoiceField(choices=('incoming', 'outgoing'))
    outstanding_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    invoices = InvoiceBriefSerializer(many=True)
    payments = PaymentBriefSerializer(many=True)
    transactions = TransactionBriefSerializer(many=True)


class RequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requisition
        fields = '__all__'


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'


class QuotationSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = '__all__'

    def get_items(self, obj):
        return QuotationItemSerializer(obj.items.all(), many=True).data


class ReceiptSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer(read_only=True)
    party_name = serializers.CharField(source='party.name', read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = '__all__'

    def get_items(self, obj):
        return ReceiptItemSerializer(obj.items.all(), many=True).data


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = '__all__'


class QuotationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = '__all__'


class ReceiptItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptItem
        fields = '__all__'


# INVOICE, DEBT AND CREDIT MANAGERS
class PartyWriteField(serializers.PrimaryKeyRelatedField):
    """
    Accepts either a Party ID (pk) or a nested object {name, email, ...} to create one.
    """
    def to_internal_value(self, data):
        if isinstance(data, dict):
            s = PartySerializer(data=data)
            s.is_valid(raise_exception=True)
            return s.save()
        return super().to_internal_value(data)


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = '__all__'


class InvoiceListSerializer(serializers.ModelSerializer):
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = Invoice
        fields = ['id', 'number', 'direction', 'issue_date', 'due_date', 'currency',
                  'total', 'paid_amount', 'amount_due', 'party', 'document']

class InvoiceCreateUpdateSerializer(serializers.ModelSerializer):
    party = PartyWriteField(queryset=Party.objects.all())
    class Meta:
        model = Invoice
        fields = ['number', 'direction', 'issue_date', 'due_date', 'currency',
                  'subtotal', 'tax', 'discount', 'total', 'party', 'document']


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['amount', 'account', 'method', 'date', 'note']

    def create(self, validated_data):
        invoice = self.context['invoice']
        user = self.context['request'].user if self.context.get('request') else None
        return FinanceService.record_invoice_payment(invoice=invoice, created_by=user, **validated_data)


class UnpaidInvoiceSerializer(serializers.ModelSerializer):
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = Invoice
        fields = ['id', 'number', 'issue_date', 'due_date', 'total', 'amount_due']


class PartyWithUnpaidSerializer(serializers.ModelSerializer):
    invoices = UnpaidInvoiceSerializer(source='unpaid_invoices', many=True, read_only=True)
    total_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = Party
        fields = ['id', 'name', 'type', 'email', 'phone', 'total_due', 'invoices']
