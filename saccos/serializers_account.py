"""
Serializers for SACCO account management (Phase 6)
Also includes simplified member creation with auto-generated credentials
"""
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.db import transaction as db_transaction
from .models import SaccoAccount, SaccoMember
from finance.models import Transaction
from finance.serializers import AccountSerializer
from common.enums import AccountType
from users.models import User
import re


class SaccoAccountSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Account"""
    account_details = AccountSerializer(source='account', read_only=True)
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    is_active = serializers.BooleanField(source='account.is_active', read_only=True)
    balance = serializers.DecimalField(source='account.balance', read_only=True, max_digits=12, decimal_places=2)
    
    class Meta:
        model = SaccoAccount
        fields = [
            'id', 'uuid', 'sacco', 'sacco_name', 'account', 'account_details',
            'bank_name', 'bank_branch', 'account_number',
            'is_active', 'balance',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'is_active', 'balance', 'created_at', 'updated_at']


class SimplifiedMemberCreateSerializer(serializers.Serializer):
    """
    Simplified serializer for creating SACCO members
    Only first_name is required - everything else is auto-generated or optional
    """
    # Required fields
    first_name = serializers.CharField(max_length=150, required=True, help_text="Member's first name")
    
    # Optional fields
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    
    # SACCO-specific optional fields
    national_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    occupation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    alternative_phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    next_of_kin_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    next_of_kin_phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    next_of_kin_relationship = serializers.CharField(max_length=100, required=False, allow_blank=True)
    role = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    def _generate_username(self, first_name):
        """
        Generate username from first name (lowercase)
        If exists, append incremental number
        """
        base_username = first_name.lower().strip()
        # Remove special characters, keep only alphanumeric
        base_username = re.sub(r'[^a-z0-9]', '', base_username)
        
        if not base_username:
            base_username = 'member'
        
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username
    
    def _generate_dummy_phone(self):
        """Generate a unique dummy phone number"""
        import random
        base = "0700000"
        counter = 0
        
        while counter < 1000:  # Safety limit
            phone = f"{base}{random.randint(100, 999)}"
            if not User.objects.filter(phone=phone).exists():
                return phone
            counter += 1
        
        # Fallback to timestamp-based
        from django.utils import timezone
        timestamp = timezone.now().timestamp()
        return f"0700{int(timestamp) % 1000000:06d}"
    
    def _generate_member_number(self, sacco):
        """
        Generate unique member number for SACCO
        Format: SACCO-{year}-{sequential_number}
        """
        from django.utils import timezone
        current_year = timezone.now().year
        
        # Get count of members in this SACCO
        member_count = SaccoMember.objects.filter(sacco=sacco).count()
        
        # Generate member number
        counter = member_count + 1
        while True:
            member_number = f"{sacco.id}-{current_year}-{counter:04d}"
            if not SaccoMember.objects.filter(sacco=sacco, member_number=member_number).exists():
                return member_number
            counter += 1
    
    @db_transaction.atomic
    def create(self, validated_data):
        """
        Create user and member automatically
        """
        sacco = self.context['sacco']
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name') or '_'
        
        # Generate username
        username = self._generate_username(first_name)
        
        # Generate password: first_name123
        password = f"{first_name.lower()}123"
        
        # Handle phone - use provided or generate dummy
        phone = validated_data.get('phone')
        if not phone:
            phone = self._generate_dummy_phone()
        
        # Handle email - can be null
        email = validated_data.get('email') or None
        
        # Generate member number
        member_number = self._generate_member_number(sacco)
        
        # Create user
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=make_password(password),
            is_active=True,
            is_verified=False,  # They can verify later
            role='Member'  # Set appropriate role
        )
        
        # Create SACCO member
        member = SaccoMember.objects.create(
            user=user,
            sacco=sacco,
            member_number=member_number,
            passbook_number=member_number,  # Use same as member number
            national_id=validated_data.get('national_id') or '',
            date_of_birth=validated_data.get('date_of_birth'),
            occupation=validated_data.get('occupation') or '',
            address=validated_data.get('address') or '',
            alternative_phone=validated_data.get('alternative_phone') or '',
            next_of_kin_name=validated_data.get('next_of_kin_name') or '',
            next_of_kin_phone=validated_data.get('next_of_kin_phone') or '',
            next_of_kin_relationship=validated_data.get('next_of_kin_relationship') or '',
            role=validated_data.get('role') or '',
            status='active',
        )
        
        # Auto-create passbook
        from .services.passbook_service import PassbookService
        PassbookService.create_passbook(member)
        
        return {
            'member': member,
            'user': user,
            'generated_username': username,
            'generated_password': password,
        }


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
