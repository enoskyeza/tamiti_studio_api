from rest_framework import serializers
from finance.models import (
    Party, Account, Invoice, Payment, Transaction,
    Goal, GoalMilestone, Requisition, Quotation, Receipt,
    InvoiceItem, QuotationItem, ReceiptItem
)
from common.enums import PartyType
from finance.services import FinanceService
from users.models import User

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


## Removed obsolete catch-all InvoiceSerializer in favor of explicit list/create serializers


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
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'party', 'party_name', 'direction', 'total', 'issue_date',
            'due_date', 'amount_due'
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
    party_email = serializers.CharField(allow_blank=True, allow_null=True)
    party_phone = serializers.CharField(allow_blank=True, allow_null=True)
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


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class RequisitionReadSerializer(serializers.ModelSerializer):
    # Return names directly for easy display
    requested_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    # Also expose explicit name fields for clarity if needed by UI
    requested_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Requisition
        fields = '__all__'

    def _name(self, user: User | None):
        if not user:
            return None
        return (user.first_name or user.username)

    def get_requested_by_name(self, obj):
        return self._name(getattr(obj, 'requested_by', None))

    def get_approved_by_name(self, obj):
        return self._name(getattr(obj, 'approved_by', None))

    def get_requested_by(self, obj):
        return self.get_requested_by_name(obj)

    def get_approved_by(self, obj):
        return self.get_approved_by_name(obj)

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


class InvoiceListSerializer(serializers.ModelSerializer):
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = Invoice
        fields = ['id', 'number', 'direction', 'issue_date', 'due_date', 'currency',
                  'total', 'paid_amount', 'amount_due', 'party', 'document']


class InvoiceItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ('name', 'description', 'quantity', 'unit_cost')


class InvoiceCreateUpdateSerializer(serializers.ModelSerializer):
    party = PartyWriteField(queryset=Party.objects.all())
    items = InvoiceItemWriteSerializer(many=True, required=False)
    class Meta:
        model = Invoice
        fields = ['number', 'direction', 'issue_date', 'due_date', 'currency',
                  'subtotal', 'tax', 'discount', 'total', 'party', 'document', 'items']

    def create(self, validated_data):
        items = validated_data.pop('items', None)
        invoice = Invoice.objects.create(**validated_data)
        if items:
            for it in items:
                InvoiceItem.objects.create(invoice=invoice, **it)
            invoice.update_total()
        else:
            if invoice.total is None:
                raise serializers.ValidationError({'total': 'Total is required when no items are provided'})
        return invoice

    def update(self, instance, validated_data):
        items = validated_data.pop('items', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for it in items:
                InvoiceItem.objects.create(invoice=instance, **it)
            instance.update_total()
        return instance


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['amount', 'account', 'method', 'date', 'notes']

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
