"""
Serializers for SACCO Account Management
"""
from rest_framework import serializers
from saccos.models import SaccoAccount
from finance.models import Transaction
from common.enums import AccountType


class SaccoAccountSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Account"""
    current_balance = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True
    )
    account_type = serializers.CharField(source='account.type', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    
    class Meta:
        model = SaccoAccount
        fields = [
            'id', 'uuid', 'sacco', 'bank_name', 'bank_branch',
            'account_number', 'current_balance', 'account_type',
            'account_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'sacco', 'current_balance', 'created_at', 'updated_at']


class CreateSaccoAccountSerializer(serializers.Serializer):
    """Serializer for creating a SACCO account"""
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bank_branch = serializers.CharField(max_length=100, required=False, allow_blank=True)
    account_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    account_type = serializers.ChoiceField(
        choices=AccountType.choices,
        default=AccountType.BANK
    )
    account_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class UpdateSaccoAccountSerializer(serializers.Serializer):
    """Serializer for updating SACCO account details"""
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bank_branch = serializers.CharField(max_length=100, required=False, allow_blank=True)
    account_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    account_type = serializers.ChoiceField(
        choices=AccountType.choices,
        required=False
    )
    account_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class SaccoAccountTransactionSerializer(serializers.ModelSerializer):
    """Serializer for SACCO account transactions"""
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'amount', 'description', 'category',
            'date', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SaccoAccountSummarySerializer(serializers.Serializer):
    """Serializer for SACCO account summary"""
    total_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_change = serializers.DecimalField(max_digits=15, decimal_places=2)
    current_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    transaction_count = serializers.IntegerField()
