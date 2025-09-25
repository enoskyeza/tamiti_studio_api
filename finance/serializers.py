from decimal import Decimal
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from comments.models import Comment
from comments.serializers import CommentSerializer
from finance.models import (
    Party, Account, Invoice, Payment, Transaction,
    Goal, GoalMilestone, Requisition, RequisitionDocument, RequisitionItem, 
    Quotation, Receipt, InvoiceItem, QuotationItem, ReceiptItem
)
from common.enums import PartyType
from finance.services import FinanceService
from users.models import User
from django.contrib.auth import get_user_model
from .models import (
    PersonalTransaction, PersonalBudget, PersonalSavingsGoal, PersonalTransactionRecurring,
    PersonalAccountTransfer, PersonalDebt, PersonalLoan, DebtPayment, LoanRepayment,
    CompanyBudget, CompanySavingsGoal, CompanyRecurringTransaction
)
from common.enums import (
    FinanceScope, PersonalExpenseCategory, PersonalIncomeSource,
    TransactionType, AccountType, BudgetPeriod
)

User = get_user_model()

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


class RequisitionDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = RequisitionDocument
        fields = '__all__'
        read_only_fields = ['uploaded_by', 'file_size', 'content_type']
    
    def get_file_url(self, obj):
        return obj.file.url if obj.file else None


class RequisitionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequisitionItem
        fields = '__all__'
        extra_kwargs = {
            'requisition': {'read_only': True}
        }
        read_only_fields = ['amount']


class RequisitionCreateUpdateSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True, required=False)
    documents = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = ['requested_by', 'approved_by', 'date_approved', 'calculated_total']
    
    def to_internal_value(self, data):
        import json
        import re
        from django.http import QueryDict
        
        # Create a mutable dictionary for normalization
        # Convert QueryDict to regular dict to avoid file object copy issues
        normalized_data = {}
        if hasattr(data, 'items'):
            for key, value in data.items():
                normalized_data[key] = value
        else:
            normalized_data = dict(data)
        
        # Handle items normalization - support multiple formats
        items_list = []
        
        # Case 1: items as JSON string (common in multipart)
        if 'items' in normalized_data:
            items_value = normalized_data['items']
            if isinstance(items_value, str):
                try:
                    items_list = json.loads(items_value)
                except json.JSONDecodeError:
                    pass  # Will be handled by validation
            elif isinstance(items_value, list):
                items_list = items_value
        
        # Case 2: items as indexed form fields (items[0][field] or items[0].field)
        else:
            # Find all item-related keys and group by index
            # Support both items[0][field] and items[0].field patterns
            item_pattern_bracket = re.compile(r'^items\[(\d+)\]\[(.+?)\]$')
            item_pattern_dot = re.compile(r'^items\[(\d+)\]\.(.+?)$')
            items_dict = {}
            
            keys_to_remove = []
            for key in list(normalized_data.keys()):
                match = item_pattern_bracket.match(key) or item_pattern_dot.match(key)
                if match:
                    index = int(match.group(1))
                    field = match.group(2)
                    
                    if index not in items_dict:
                        items_dict[index] = {}
                    
                    # Get the value
                    value = normalized_data[key]
                    items_dict[index][field] = value
                    keys_to_remove.append(key)
            
            # Convert to list and remove original keys
            if items_dict:
                items_list = [items_dict[i] for i in sorted(items_dict.keys())]
                
                # Remove the original form field keys
                for key in keys_to_remove:
                    normalized_data.pop(key, None)
        
        # Set normalized items
        if items_list:
            normalized_data['items'] = items_list
        
        # Normalize documents: always extract from request.FILES to ensure a list of UploadedFile
        try:
            request = self.context.get('request')
            if request is not None and hasattr(request, 'FILES'):
                documents_list = request.FILES.getlist('documents')
                if documents_list:
                    normalized_data['documents'] = documents_list
        except Exception:
            # Do not fail normalization on document extraction issues; let DRF validation handle
            pass
            
        return super().to_internal_value(normalized_data)
    
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        documents_data = validated_data.pop('documents', [])
        
        # Set has_items flag
        validated_data['has_items'] = len(items_data) > 0
        validated_data['requested_by'] = self.context['request'].user
        
        requisition = Requisition.objects.create(**validated_data)
        
        # Create items
        for item_data in items_data:
            RequisitionItem.objects.create(requisition=requisition, **item_data)
        
        # Handle file uploads
        for file_obj in documents_data:
            RequisitionDocument.objects.create(
                requisition=requisition,
                file=file_obj,
                filename=file_obj.name,
                file_size=file_obj.size,
                content_type=file_obj.content_type,
                uploaded_by=self.context['request'].user
            )
        
        return requisition
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        documents_data = validated_data.pop('documents', [])
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update has_items flag if items are provided
        if items_data is not None:
            instance.has_items = len(items_data) > 0
            # Clear existing items and create new ones
            instance.items.all().delete()
            for item_data in items_data:
                RequisitionItem.objects.create(requisition=instance, **item_data)
        
        # Handle new file uploads
        for file_obj in documents_data:
            RequisitionDocument.objects.create(
                requisition=instance,
                file=file_obj,
                filename=file_obj.name,
                file_size=file_obj.size,
                content_type=file_obj.content_type,
                uploaded_by=self.context['request'].user
            )
        
        instance.save()
        return instance


class RequisitionDetailSerializer(serializers.ModelSerializer):
    items = RequisitionItemSerializer(many=True, read_only=True)
    documents = RequisitionDocumentSerializer(many=True, read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    can_approve = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    comment_count = serializers.ReadOnlyField()
    document_count = serializers.ReadOnlyField()
    effective_total = serializers.ReadOnlyField()
    activity_comments = serializers.SerializerMethodField()
    
    class Meta:
        model = Requisition
        fields = '__all__'
    
    def get_can_approve(self, obj):
        user = self.context['request'].user
        return obj.can_approve(user)
    
    def get_can_edit(self, obj):
        user = self.context['request'].user
        return obj.can_edit(user)
    
    def get_can_delete(self, obj):
        user = self.context['request'].user
        return obj.can_delete(user)

    def get_activity_comments(self, obj):
        # Return comments for this requisition ordered by created_at
        ct = ContentType.objects.get_for_model(obj.__class__)
        qs = Comment.objects.filter(content_type=ct, object_id=obj.id).order_by('created_at')
        return CommentSerializer(qs, many=True, context=self.context).data


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

# ===================== PERSONAL FINANCE SERIALIZERS =====================

class PersonalAccountListSerializer(serializers.ModelSerializer):
    """Serializer for listing personal accounts"""
    balance_display = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'number', 'type', 'type_display', 'balance',
            'balance_display', 'currency', 'currency_display', 'is_active',
            'description', 'created_at', 'updated_at'
        ]

    def get_balance_display(self, obj):
        return f"{obj.currency} {obj.balance:,.2f}"


class PersonalAccountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating personal accounts"""

    class Meta:
        model = Account
        fields = ['name', 'number', 'type', 'currency', 'description']

    def validate_type(self, value):
        personal_account_types = [
            AccountType.PERSONAL_BANK, AccountType.AIRTEL_MONEY, AccountType.MTN_MONEY,
            AccountType.CASH_WALLET, AccountType.SAVINGS_ACCOUNT, AccountType.CREDIT_CARD
        ]
        if value not in personal_account_types:
            raise serializers.ValidationError("Invalid account type for personal accounts")
        return value

    def create(self, validated_data):
        validated_data['scope'] = FinanceScope.PERSONAL
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class PersonalAccountUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating personal accounts"""

    class Meta:
        model = Account
        fields = ['name', 'number', 'description', 'is_active']


class PersonalTransactionListSerializer(serializers.ModelSerializer):
    """Serializer for listing personal transactions with enhanced display"""
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_type = serializers.CharField(source='account.get_type_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    income_source_display = serializers.CharField(source='get_income_source_display', read_only=True)
    expense_category_display = serializers.CharField(source='get_expense_category_display', read_only=True)
    total_cost = serializers.ReadOnlyField()
    formatted_amount = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()

    class Meta:
        model = PersonalTransaction
        fields = [
            'id', 'type', 'type_display', 'amount', 'formatted_amount', 'account_name',
            'account_type', 'description', 'transaction_charge', 'total_cost',
            'income_source', 'income_source_display', 'expense_category',
            'expense_category_display', 'reason', 'date', 'formatted_date',
            'reference_number', 'receipt_image', 'tags', 'location', 'notes',
            'is_recurring', 'created_at'
        ]

    def get_formatted_amount(self, obj):
        return f"{obj.account.currency} {obj.amount:,.2f}"

    def get_formatted_date(self, obj):
        return obj.date.strftime('%Y-%m-%d %H:%M')


class PersonalTransactionDetailSerializer(PersonalTransactionListSerializer):
    """Detailed serializer for single transaction view"""
    account = PersonalAccountListSerializer(read_only=True)
    recurring_instances = serializers.SerializerMethodField()

    class Meta(PersonalTransactionListSerializer.Meta):
        fields = PersonalTransactionListSerializer.Meta.fields + ['account', 'recurring_instances']

    def get_recurring_instances(self, obj):
        if obj.is_recurring and hasattr(obj, 'recurring_instances'):
            return obj.recurring_instances.count()
        return 0


class PersonalTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating personal transactions"""
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(scope=FinanceScope.PERSONAL)
    )

    class Meta:
        model = PersonalTransaction
        fields = [
            'type', 'amount', 'account', 'description', 'transaction_charge',
            'income_source', 'expense_category', 'reason', 'date',
            'reference_number', 'receipt_image', 'tags', 'location', 'notes'
        ]

    def validate_account(self, value):
        user = self.context['request'].user
        if value.owner != user:
            raise serializers.ValidationError("Account must belong to the current user")
        return value

    def validate(self, data):
        if data['type'] == TransactionType.INCOME and not data.get('income_source'):
            raise serializers.ValidationError({
                'income_source': 'Income source is required for income transactions'
            })

        if data['type'] == TransactionType.EXPENSE and not data.get('expense_category'):
            raise serializers.ValidationError({
                'expense_category': 'Expense category is required for expense transactions'
            })

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PersonalTransactionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating personal transactions"""

    class Meta:
        model = PersonalTransaction
        fields = [
            'description', 'transaction_charge', 'reason', 'reference_number',
            'receipt_image', 'tags', 'location', 'notes'
        ]


class PersonalBudgetListSerializer(serializers.ModelSerializer):
    """Serializer for listing personal budgets"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    remaining_amount = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()
    is_exceeded = serializers.ReadOnlyField()
    should_alert = serializers.ReadOnlyField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = PersonalBudget
        fields = [
            'id', 'name', 'category', 'category_display', 'period', 'period_display',
            'allocated_amount', 'spent_amount', 'remaining_amount', 'progress_percentage',
            'start_date', 'end_date', 'is_active', 'alert_threshold',
            'is_exceeded', 'should_alert', 'status', 'created_at'
        ]

    def get_status(self, obj):
        if obj.is_exceeded:
            return 'over_budget'
        elif obj.should_alert:
            return 'warning'
        else:
            return 'on_track'


class PersonalBudgetCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating personal budgets"""

    class Meta:
        model = PersonalBudget
        fields = [
            'name', 'category', 'period', 'allocated_amount', 'start_date',
            'end_date', 'alert_threshold'
        ]

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PersonalBudgetUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating personal budgets"""

    class Meta:
        model = PersonalBudget
        fields = ['name', 'allocated_amount', 'alert_threshold', 'is_active']


class PersonalSavingsGoalListSerializer(serializers.ModelSerializer):
    """Serializer for listing savings goals"""
    progress_percentage = serializers.ReadOnlyField()
    remaining_amount = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    required_monthly_savings = serializers.ReadOnlyField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = PersonalSavingsGoal
        fields = [
            'id', 'name', 'description', 'target_amount', 'current_amount',
            'progress_percentage', 'remaining_amount', 'target_date', 'days_remaining',
            'required_monthly_savings', 'is_active', 'is_achieved', 'achieved_date',
            'status', 'created_at'
        ]

    def get_status(self, obj):
        if obj.is_achieved:
            return 'achieved'
        elif obj.days_remaining == 0:
            return 'overdue'
        elif obj.days_remaining <= 30:
            return 'urgent'
        else:
            return 'active'


class PersonalSavingsGoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating savings goals"""

    class Meta:
        model = PersonalSavingsGoal
        fields = [
            'name', 'description', 'target_amount', 'target_date',
            'auto_save_amount', 'auto_save_frequency'
        ]

    def validate_target_date(self, value):
        from django.utils import timezone
        if value <= timezone.now().date():
            raise serializers.ValidationError("Target date must be in the future")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PersonalSavingsGoalUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating savings goals"""

    class Meta:
        model = PersonalSavingsGoal
        fields = [
            'name', 'description', 'target_amount', 'target_date',
            'auto_save_amount', 'auto_save_frequency', 'is_active'
        ]


class PersonalSavingsContributionSerializer(serializers.Serializer):
    """Serializer for adding contributions to savings goals"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=200, default="Manual contribution")


class PersonalTransactionRecurringListSerializer(serializers.ModelSerializer):
    """Serializer for listing recurring transactions"""
    account_name = serializers.CharField(source='account.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    income_source_display = serializers.CharField(source='get_income_source_display', read_only=True)
    expense_category_display = serializers.CharField(source='get_expense_category_display', read_only=True)

    class Meta:
        model = PersonalTransactionRecurring
        fields = [
            'id', 'name', 'type', 'type_display', 'amount', 'account_name',
            'description', 'frequency', 'frequency_display', 'start_date', 'end_date',
            'income_source', 'income_source_display', 'expense_category',
            'expense_category_display', 'is_active', 'next_due_date', 'last_created_date'
        ]


class PersonalTransactionRecurringCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating recurring transactions"""
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(scope=FinanceScope.PERSONAL)
    )

    class Meta:
        model = PersonalTransactionRecurring
        fields = [
            'name', 'type', 'amount', 'account', 'description', 'frequency',
            'start_date', 'end_date', 'income_source', 'expense_category'
        ]

    def validate_account(self, value):
        user = self.context['request'].user
        if value.owner != user:
            raise serializers.ValidationError("Account must belong to the current user")
        return value

    def validate(self, data):
        if data['type'] == TransactionType.INCOME and not data.get('income_source'):
            raise serializers.ValidationError({
                'income_source': 'Income source is required for income transactions'
            })

        if data['type'] == TransactionType.EXPENSE and not data.get('expense_category'):
            raise serializers.ValidationError({
                'expense_category': 'Expense category is required for expense transactions'
            })

        if data.get('end_date') and data['end_date'] <= data['start_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['next_due_date'] = validated_data['start_date']
        return super().create(validated_data)


class PersonalTransactionRecurringUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating recurring transactions"""

    class Meta:
        model = PersonalTransactionRecurring
        fields = ['name', 'amount', 'description', 'end_date', 'is_active']


# ===================== ANALYTICS SERIALIZERS =====================

class PersonalFinanceAnalyticsSerializer(serializers.Serializer):
    """Serializer for personal finance analytics data"""
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transaction_charges = serializers.DecimalField(max_digits=12, decimal_places=2)

    # Category breakdowns
    expense_by_category = serializers.DictField()
    income_by_source = serializers.DictField()

    # Monthly trends
    monthly_trends = serializers.ListField()

    # Account balances
    account_balances = serializers.ListField()

    # Budget performance
    budget_performance = serializers.ListField()

    # Savings progress
    savings_progress = serializers.ListField()


class PersonalMonthlySummarySerializer(serializers.Serializer):
    """Serializer for monthly financial summary"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    month_name = serializers.CharField()
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transaction_charges = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()
    income_transaction_count = serializers.IntegerField()
    expense_transaction_count = serializers.IntegerField()
    income_by_source = serializers.DictField()
    expenses_by_category = serializers.DictField()
    average_transaction_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class PersonalSpendingInsightsSerializer(serializers.Serializer):
    """Serializer for spending insights and analytics"""
    period_days = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_daily_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_daily_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    highest_expense_day = serializers.DictField(allow_null=True)
    top_expense_categories = serializers.ListField()
    spending_trend = serializers.CharField()
    transaction_count = serializers.IntegerField()
    expense_transaction_count = serializers.IntegerField()


class PersonalCategoryBreakdownSerializer(serializers.Serializer):
    """Serializer for expense category breakdown"""
    period_days = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    categories = serializers.ListField()


# Account Transfer Serializers
class PersonalAccountTransferListSerializer(serializers.ModelSerializer):
    """Serializer for listing account transfers"""
    from_account_name = serializers.CharField(source='from_account.name', read_only=True)
    to_account_name = serializers.CharField(source='to_account.name', read_only=True)
    total_debit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PersonalAccountTransfer
        fields = [
            'id', 'from_account', 'from_account_name', 'to_account', 'to_account_name',
            'amount', 'transfer_fee', 'total_debit_amount', 'exchange_rate',
            'description', 'reference_number', 'date', 'created_at'
        ]


class PersonalAccountTransferCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating account transfers"""
    
    class Meta:
        model = PersonalAccountTransfer
        fields = [
            'from_account', 'to_account', 'amount', 'transfer_fee', 
            'exchange_rate', 'description', 'reference_number', 'date'
        ]

    def validate(self, data):
        if data['from_account'] == data['to_account']:
            raise serializers.ValidationError("Cannot transfer to the same account")
        
        # Validate account ownership
        user = self.context['request'].user
        if (data['from_account'].owner != user or 
            data['to_account'].owner != user or
            data['from_account'].scope != FinanceScope.PERSONAL or
            data['to_account'].scope != FinanceScope.PERSONAL):
            raise serializers.ValidationError("Both accounts must be personal accounts owned by you")
        
        return data

    def create(self, validated_data):
        from finance.services import PersonalFinanceService
        user = self.context['request'].user
        return PersonalFinanceService.create_account_transfer(user, validated_data)


# Debt Management Serializers
class PersonalDebtListSerializer(serializers.ModelSerializer):
    """Serializer for listing personal debts"""
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = PersonalDebt
        fields = [
            'id', 'creditor_name', 'creditor_contact', 'principal_amount',
            'current_balance', 'remaining_balance', 'total_paid', 'interest_rate',
            'has_interest', 'borrowed_date', 'due_date', 'days_until_due',
            'is_active', 'is_fully_paid', 'is_overdue', 'paid_date',
            'description', 'notes', 'created_at'
        ]

    def get_days_until_due(self, obj):
        from django.utils import timezone
        if obj.due_date:
            delta = obj.due_date - timezone.now().date()
            return delta.days
        return None


class PersonalDebtCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating personal debts"""
    
    class Meta:
        model = PersonalDebt
        fields = [
            'creditor_name', 'creditor_contact', 'principal_amount',
            'current_balance', 'interest_rate', 'has_interest',
            'borrowed_date', 'due_date', 'description', 'notes'
        ]

    def create(self, validated_data):
        from finance.services import PersonalFinanceService
        user = self.context['request'].user
        return PersonalFinanceService.create_personal_debt(user, validated_data)


class PersonalLoanListSerializer(serializers.ModelSerializer):
    """Serializer for listing personal loans"""
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_repaid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = PersonalLoan
        fields = [
            'id', 'borrower_name', 'borrower_contact', 'principal_amount',
            'current_balance', 'remaining_balance', 'total_repaid', 'interest_rate',
            'has_interest', 'loan_date', 'due_date', 'days_until_due',
            'is_active', 'is_fully_repaid', 'is_overdue', 'repaid_date',
            'description', 'notes', 'created_at'
        ]

    def get_days_until_due(self, obj):
        from django.utils import timezone
        if obj.due_date:
            delta = obj.due_date - timezone.now().date()
            return delta.days
        return None


class PersonalLoanCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating personal loans"""
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(scope=FinanceScope.PERSONAL)
    )
    
    class Meta:
        model = PersonalLoan
        fields = [
            'borrower_name', 'borrower_contact', 'principal_amount',
            'current_balance', 'interest_rate', 'has_interest',
            'loan_date', 'due_date', 'description', 'notes', 'account'
        ]

    def validate_account(self, value):
        user = self.context['request'].user
        if value.owner != user:
            raise serializers.ValidationError("Account must belong to you")
        return value

    def create(self, validated_data):
        from finance.services import PersonalFinanceService
        user = self.context['request'].user
        return PersonalFinanceService.create_personal_loan(user, validated_data)


class DebtPaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing debt payments"""
    debt_creditor = serializers.CharField(source='debt.creditor_name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = DebtPayment
        fields = [
            'id', 'debt', 'debt_creditor', 'amount', 'payment_date',
            'account', 'account_name', 'notes', 'created_at'
        ]


class DebtPaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating debt payments"""
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(scope=FinanceScope.PERSONAL)
    )
    
    class Meta:
        model = DebtPayment
        fields = ['amount', 'account', 'payment_date', 'notes']

    def validate_account(self, value):
        user = self.context['request'].user
        if value.owner != user:
            raise serializers.ValidationError("Account must belong to you")
        return value

    def create(self, validated_data):
        from finance.services import PersonalFinanceService
        user = self.context['request'].user
        debt_id = self.context['debt_id']
        return PersonalFinanceService.make_debt_payment(user, debt_id, validated_data)


class LoanRepaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing loan repayments"""
    loan_borrower = serializers.CharField(source='loan.borrower_name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = LoanRepayment
        fields = [
            'id', 'loan', 'loan_borrower', 'amount', 'repayment_date',
            'account', 'account_name', 'notes', 'created_at'
        ]


class LoanRepaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating loan repayments"""
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(scope=FinanceScope.PERSONAL)
    )
    
    class Meta:
        model = LoanRepayment
        fields = ['amount', 'account', 'repayment_date', 'notes']

    def validate_account(self, value):
        user = self.context['request'].user
        if value.owner != user:
            raise serializers.ValidationError("Account must belong to you")
        return value

    def create(self, validated_data):
        from finance.services import PersonalFinanceService
        user = self.context['request'].user
        loan_id = self.context['loan_id']
        return PersonalFinanceService.receive_loan_repayment(user, loan_id, validated_data)


class DebtSummarySerializer(serializers.Serializer):
    """Serializer for debt and loan summary"""
    total_debt_owed = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_loans_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_debt_position = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_debts_count = serializers.IntegerField()
    active_loans_count = serializers.IntegerField()
    overdue_debts_count = serializers.IntegerField()
    overdue_loans_count = serializers.IntegerField()
    overdue_debts = PersonalDebtListSerializer(many=True)
    overdue_loans = PersonalLoanListSerializer(many=True)


# COMPANY FINANCE SERIALIZERS

class CompanyBudgetListSerializer(serializers.ModelSerializer):
    """Serializer for listing company budgets"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    spent_percentage = serializers.ReadOnlyField()
    remaining_amount = serializers.ReadOnlyField()
    is_over_budget = serializers.ReadOnlyField()
    is_near_limit = serializers.ReadOnlyField()
    
    class Meta:
        model = CompanyBudget
        fields = [
            'id', 'name', 'department', 'department_name', 'category', 'period',
            'allocated_amount', 'spent_amount', 'spent_percentage', 'remaining_amount',
            'start_date', 'end_date', 'is_active', 'alert_threshold',
            'is_over_budget', 'is_near_limit', 'approved_by', 'approved_at',
            'created_at', 'updated_at'
        ]


class CompanyBudgetCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating company budgets"""
    
    class Meta:
        model = CompanyBudget
        fields = [
            'name', 'department', 'category', 'period', 'allocated_amount',
            'start_date', 'end_date', 'is_active', 'alert_threshold'
        ]

    def validate(self, data):
        if data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        return data


class CompanyBudgetUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating company budgets"""
    
    class Meta:
        model = CompanyBudget
        fields = [
            'name', 'allocated_amount', 'end_date', 'is_active', 'alert_threshold'
        ]


class CompanySavingsGoalListSerializer(serializers.ModelSerializer):
    """Serializer for listing company savings goals"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    savings_account_name = serializers.CharField(source='savings_account.name', read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    remaining_amount = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = CompanySavingsGoal
        fields = [
            'id', 'name', 'description', 'department', 'department_name',
            'target_amount', 'current_amount', 'progress_percentage', 'remaining_amount',
            'start_date', 'target_date', 'days_remaining', 'is_active', 'priority',
            'savings_account', 'savings_account_name', 'is_completed',
            'created_at', 'updated_at'
        ]


class CompanySavingsGoalCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating company savings goals"""
    
    class Meta:
        model = CompanySavingsGoal
        fields = [
            'name', 'description', 'department', 'target_amount', 'current_amount',
            'start_date', 'target_date', 'is_active', 'priority', 'savings_account'
        ]

    def validate(self, data):
        if data['start_date'] >= data['target_date']:
            raise serializers.ValidationError("Target date must be after start date")
        if data.get('current_amount', 0) > data['target_amount']:
            raise serializers.ValidationError("Current amount cannot exceed target amount")
        return data


class CompanySavingsGoalUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating company savings goals"""
    
    class Meta:
        model = CompanySavingsGoal
        fields = [
            'name', 'description', 'target_amount', 'current_amount',
            'target_date', 'is_active', 'priority', 'savings_account'
        ]

    def validate(self, data):
        if 'current_amount' in data and 'target_amount' in data:
            if data['current_amount'] > data['target_amount']:
                raise serializers.ValidationError("Current amount cannot exceed target amount")
        return data


class CompanyRecurringTransactionListSerializer(serializers.ModelSerializer):
    """Serializer for listing company recurring transactions"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    is_due = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = CompanyRecurringTransaction
        fields = [
            'id', 'name', 'department', 'department_name', 'amount', 'transaction_type',
            'category', 'account', 'account_name', 'frequency', 'start_date', 'end_date',
            'next_due_date', 'is_active', 'auto_create', 'requires_approval',
            'approved_by', 'approved_by_name', 'is_due', 'is_overdue',
            'last_created_date', 'total_created', 'created_at', 'updated_at'
        ]


class CompanyRecurringTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating company recurring transactions"""
    
    class Meta:
        model = CompanyRecurringTransaction
        fields = [
            'name', 'department', 'amount', 'transaction_type', 'category',
            'account', 'frequency', 'start_date', 'end_date', 'next_due_date',
            'is_active', 'auto_create', 'requires_approval'
        ]

    def validate(self, data):
        if data.get('end_date') and data['start_date'] >= data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        if data['next_due_date'] < data['start_date']:
            raise serializers.ValidationError("Next due date cannot be before start date")
        return data


class CompanyRecurringTransactionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating company recurring transactions"""
    
    class Meta:
        model = CompanyRecurringTransaction
        fields = [
            'name', 'amount', 'category', 'account', 'frequency',
            'end_date', 'next_due_date', 'is_active', 'auto_create', 'requires_approval'
        ]
