from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Event, EventMembership, BatchMembership,
    TicketType, Batch, Ticket, ScanLog, BatchExport, TemporaryUser,
)

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'name', 'phone', 'role', 
                 'is_temporary', 'expires_at', 'created_for_event', 'is_expired']
    
    def get_name(self, obj):
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username
    
    def get_is_expired(self, obj):
        return obj.is_expired() if hasattr(obj, 'is_expired') else False


class EventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    stats = serializers.SerializerMethodField()
    ticket_types = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'date', 'venue', 'status',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 
            'stats', 'ticket_types'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_stats(self, obj):
        """Get event-specific statistics"""
        from .models import Ticket
        
        # Get all tickets for this event
        tickets = Ticket.objects.filter(batch__event=obj)
        
        total_batches = obj.batches.count()
        total_tickets = tickets.count()
        activated_tickets = tickets.filter(status__in=['activated', 'scanned']).count()
        scanned_tickets = tickets.filter(status='scanned').count()
        unused_tickets = tickets.filter(status='unused').count()
        voided_tickets = tickets.filter(status='void').count()
        
        return {
            'total_batches': total_batches,
            'total_tickets': total_tickets,
            'activated_tickets': activated_tickets,
            'scanned_tickets': scanned_tickets,
            'unused_tickets': unused_tickets,
            'voided_tickets': voided_tickets,
        }
    
    def get_ticket_types(self, obj):
        """Get ticket types for this event"""
        ticket_types = obj.ticket_types.filter(is_active=True).order_by('name')
        return TicketTypeSerializer(ticket_types, many=True).data




class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = [
            'id', 'event', 'name', 'price', 'description', 'max_quantity',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BatchLayoutSerializer(serializers.Serializer):
    columns = serializers.IntegerField(min_value=1, max_value=20)
    rows = serializers.IntegerField(min_value=1, max_value=50)
    qr_size = serializers.IntegerField(min_value=10, max_value=50)
    include_short_code = serializers.BooleanField()


class BatchCreateSerializer(serializers.ModelSerializer):
    # Accept frontend field names and map them to backend fields
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    layout_columns = serializers.IntegerField(min_value=1, max_value=20)
    layout_rows = serializers.IntegerField(min_value=1, max_value=50)
    qr_size = serializers.IntegerField(min_value=10, max_value=50)
    include_short_code = serializers.BooleanField()
    
    class Meta:
        model = Batch
        fields = [
            'event', 'quantity', 'layout_columns', 'layout_rows', 
            'qr_size', 'include_short_code'
        ]
    
    def validate(self, data):
        """Validate batch creation data"""
        quantity = data.get('quantity', 0)
        columns = data.get('layout_columns', 1)
        rows = data.get('layout_rows', 1)
        
        # Validate quantity constraints
        if quantity < 1 or quantity > 10000:
            raise serializers.ValidationError("Quantity must be between 1 and 10,000")
        
        # Validate grid capacity
        grid_capacity = columns * rows
        if quantity > grid_capacity:
            raise serializers.ValidationError(
                f"Grid layout ({columns}x{rows}) can only fit {grid_capacity} codes. "
                f"Reduce quantity to {grid_capacity} or increase grid size."
            )
        
        # Validate event is active
        event = data.get('event')
        if event and event.status != 'active':
            raise serializers.ValidationError("Cannot create batch for inactive event")
        
        return data
    
    def create(self, validated_data):
        import secrets
        import string
        import uuid
        from django.db import transaction
        
        # Set the created_by field
        validated_data['created_by'] = self.context['request'].user
        
        def generate_unique_short_code():
            while True:
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                if not Ticket.objects.filter(short_code=code).exists():
                    return code
        
        def generate_unique_qr_code():
            while True:
                code = f"TT{uuid.uuid4().hex[:16].upper()}"
                if not Ticket.objects.filter(qr_code=code).exists():
                    return code
        
        batch = Batch.objects.create(**validated_data)
        
        # Create tickets with pre-generated unique codes
        tickets = []
        for i in range(batch.quantity):
            ticket = Ticket(
                batch=batch,
                short_code=generate_unique_short_code(),
                qr_code=generate_unique_qr_code()
            )
            tickets.append(ticket)
        
        # Bulk create tickets with pre-generated codes
        Ticket.objects.bulk_create(tickets)
        
        # Return the batch instance, not serialized data
        return batch


class BatchSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    layout = serializers.SerializerMethodField()
    ticket_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'batch_number', 'event', 'event_name', 'quantity', 'ticket_count',
            'activated_count', 'scanned_count', 'voided_count', 'unused_count',
            'status', 'created_by', 'created_by_name', 'created_at',
            'voided_at', 'voided_by', 'void_reason', 'layout',
            'layout_columns', 'layout_rows', 'qr_size', 'include_short_code'
        ]
        read_only_fields = [
            'id', 'batch_number', 'activated_count', 'scanned_count',
            'voided_count', 'unused_count', 'created_by', 'created_at',
            'ticket_count'
        ]
    
    def get_layout(self, obj):
        return {
            'columns': obj.layout_columns,
            'rows': obj.layout_rows,
            'qr_size': obj.qr_size,
            'qrSize': obj.qr_size,  # Legacy support
            'include_short_code': obj.include_short_code,
            'includeShortCode': obj.include_short_code,  # Legacy support
        }

    def get_ticket_count(self, obj):
        return obj.tickets.count()


class BuyerInfoSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    ticket_type_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class TicketSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    event_name = serializers.CharField(source='batch.event.name', read_only=True)
    event_date = serializers.CharField(source='batch.event.date', read_only=True)
    activated_by_name = serializers.CharField(source='activated_by.username', read_only=True)
    scanned_by_name = serializers.CharField(source='scanned_by.username', read_only=True)
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)
    buyer_info = serializers.SerializerMethodField()
    activated_by = serializers.SerializerMethodField()
    scanned_by = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'batch', 'batch_number', 'event_name', 'event_date', 'short_code', 'qr_code',
            'status', 'buyer_name', 'buyer_phone', 'buyer_email', 'ticket_type',
            'ticket_type_name', 'notes', 'activated_at', 'activated_by',
            'activated_by_name', 'scanned_at', 'scanned_by', 'scanned_by_name',
            'gate', 'created_at', 'buyer_info'
        ]
        read_only_fields = [
            'id', 'short_code', 'qr_code', 'activated_at', 'activated_by',
            'scanned_at', 'scanned_by', 'created_at'
        ]
    
    def get_activated_by(self, obj):
        if obj.activated_by:
            return {
                'id': obj.activated_by.id,
                'username': obj.activated_by.username,
                'email': obj.activated_by.email
            }
        return None
    
    def get_scanned_by(self, obj):
        if obj.scanned_by:
            return {
                'id': obj.scanned_by.id,
                'username': obj.scanned_by.username,
                'email': obj.scanned_by.email
            }
        return None
    
    def get_buyer_info(self, obj):
        buyer_info = {}
        if obj.buyer_name:
            buyer_info['name'] = obj.buyer_name
        if obj.buyer_phone:
            buyer_info['phone'] = obj.buyer_phone
        if obj.buyer_email:
            buyer_info['email'] = obj.buyer_email
        return buyer_info if buyer_info else None


class TicketActivateSerializer(serializers.Serializer):
    qr_code = serializers.CharField(max_length=255)
    buyer_info = serializers.DictField(required=False)
    event_id = serializers.IntegerField(required=False)


class TicketVerifySerializer(serializers.Serializer):
    qr_code = serializers.CharField(max_length=255)
    gate = serializers.CharField(max_length=50, required=False, allow_blank=True)
    event_id = serializers.IntegerField(required=False)


class ScanResultSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    ticket = TicketSerializer(required=False)
    error = serializers.CharField(required=False)
    duplicate_info = serializers.DictField(required=False)


class ScanLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    ticket_code = serializers.CharField(source='ticket.short_code', read_only=True)
    
    class Meta:
        model = ScanLog
        fields = [
            'id', 'ticket', 'ticket_code', 'qr_code', 'scan_type', 'result',
            'user', 'user_name', 'gate', 'error_message', 'ip_address',
            'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BatchExportSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    exported_by_name = serializers.CharField(source='exported_by.username', read_only=True)
    
    class Meta:
        model = BatchExport
        fields = [
            'id', 'batch', 'batch_number', 'export_type', 'file_path',
            'file_size', 'exported_by', 'exported_by_name', 'created_at',
            'downloaded_at', 'download_count'
        ]
        read_only_fields = [
            'id', 'file_path', 'file_size', 'exported_by', 'created_at',
            'downloaded_at', 'download_count'
        ]


class BatchStatsSerializer(serializers.Serializer):
    total_batches = serializers.IntegerField()
    total_tickets = serializers.IntegerField()
    activated_tickets = serializers.IntegerField()
    scanned_tickets = serializers.IntegerField()
    unused_tickets = serializers.IntegerField()
    voided_tickets = serializers.IntegerField()


class EventStatsSerializer(serializers.Serializer):
    event = EventSerializer()
    total_tickets = serializers.IntegerField()
    activated_tickets = serializers.IntegerField()
    scanned_tickets = serializers.IntegerField()
    activation_rate = serializers.FloatField()
    scan_rate = serializers.FloatField()




class TemporaryUserSerializer(serializers.ModelSerializer):
    """DEPRECATED: Use UserSerializer with is_temporary=True instead"""
    event_name = serializers.CharField(source='event.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = TemporaryUser
        fields = [
            'id', 'username', 'event', 'event_name', 'role', 'is_active',
            'expires_at', 'created_by', 'created_by_name', 'can_activate',
            'can_verify', 'can_scan', 'last_login', 'login_count', 'created_at', 'is_expired'
        ]
        read_only_fields = ['created_by', 'last_login', 'login_count', 'created_at']
    
    def get_is_expired(self, obj):
        return obj.is_expired()


class TemporaryUserCreateSerializer(serializers.ModelSerializer):
    """Create temporary Users with the unified User model"""
    password = serializers.CharField(write_only=True, min_length=6, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    created_for_event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.all()
    )
    # Legacy permission fields for backward compatibility
    can_activate = serializers.BooleanField(write_only=True, default=True)
    can_verify = serializers.BooleanField(write_only=True, default=True)
    can_scan = serializers.BooleanField(write_only=True, default=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'confirm_password', 
            'created_for_event', 'expires_at', 'is_temporary',
            'can_activate', 'can_verify', 'can_scan'
        ]
        extra_kwargs = {
            'is_temporary': {'default': True},
            'email': {'required': False}
        }
    
    def validate(self, data):
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise serializers.ValidationError("Passwords don't match")
        return data
    
    def create(self, validated_data):
        # Extract permission flags
        can_activate = validated_data.pop('can_activate', True)
        can_verify = validated_data.pop('can_verify', True) 
        can_scan = validated_data.pop('can_scan', True)
        
        # Handle password
        password = validated_data.pop('password', None)
        validated_data.pop('confirm_password', None)
        
        # Get event
        event = validated_data.get('created_for_event')
        if not event:
            raise serializers.ValidationError("Event is required for temporary users")
        
        # Use the User model's create_temporary_user method
        # Don't pass email as extra_field since create_temporary_user sets it
        extra_fields = {}
        if validated_data.get('email'):
            extra_fields['email'] = validated_data.get('email')
            
        user, generated_password = User.create_temporary_user(
            event=event,
            username=validated_data.get('username'),
            password=password,
            expires_at=validated_data.get('expires_at'),
            **extra_fields
        )
        
        # Create EventMembership with permissions
        from .models import EventMembership
        permissions = {}
        if can_activate:
            permissions['activate_tickets'] = True
        if can_verify or can_scan:
            permissions['verify_tickets'] = True
            
        EventMembership.objects.create(
            user=user,
            event=event,
            role='staff',
            permissions=permissions,
            invited_by=self.context['request'].user
        )
        
        # Store generated password for response
        user._generated_password = generated_password if not password else None
        return user


class TemporaryUserLoginSerializer(serializers.Serializer):
    """DEPRECATED: Use standard JWT authentication instead"""
    username = serializers.CharField()
    password = serializers.CharField()
    event_id = serializers.IntegerField(required=False)


class EventMembershipSerializer(serializers.ModelSerializer):
    """Serializer for the new unified EventMembership model"""
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    event_name = serializers.CharField(source='event.name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.username', read_only=True)
    is_expired = serializers.SerializerMethodField()
    assigned_by = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    assigned_at = serializers.SerializerMethodField()

    class Meta:
        model = EventMembership
        fields = [
            'id', 'user', 'user_id', 'event', 'event_name', 'role', 'permissions',
            'invited_by', 'invited_by_name', 'invited_at', 'assigned_by',
            'assigned_by_name', 'assigned_at', 'expires_at', 'is_active',
            'is_expired', 'created_at', 'updated_at', 'username', 'email'
        ]
        read_only_fields = [
            'id', 'invited_at', 'assigned_by', 'assigned_by_name', 'assigned_at',
            'is_expired', 'created_at', 'updated_at', 'username', 'email'
        ]

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_assigned_by(self, obj):
        return obj.invited_by_id if obj.invited_by_id else None

    def get_assigned_by_name(self, obj):
        if not obj.invited_by:
            return None
        full_name = f"{obj.invited_by.first_name} {obj.invited_by.last_name}".strip()
        return full_name if full_name else obj.invited_by.username

    def get_assigned_at(self, obj):
        timestamp = obj.invited_at or getattr(obj, 'created_at', None)
        return timestamp.isoformat() if timestamp else None

    def validate_user_id(self, value):
        """Validate that the user exists"""
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")
    
    def validate(self, attrs):
        """Validate membership constraints"""
        user_id = attrs.get('user_id')
        event = attrs.get('event')
        has_permissions = 'permissions' in attrs
        permissions = attrs.get('permissions') if has_permissions else None

        if user_id and event:
            # Check for existing membership
            if EventMembership.objects.filter(user_id=user_id, event=event).exists():
                raise serializers.ValidationError("User is already a member of this event")
        
        if has_permissions:
            # Convert legacy list permissions to dict format
            if isinstance(permissions, list):
                permission_dict = {perm: True for perm in permissions}
                attrs['permissions'] = permission_dict
            elif permissions is None:
                if self.instance:
                    # Leave existing permissions unchanged on updates
                    attrs.pop('permissions', None)
                else:
                    attrs['permissions'] = {}
        elif not self.instance:
            attrs['permissions'] = {}
        
        return attrs
    
    def create(self, validated_data):
        """Create EventMembership with proper user_id handling"""
        user_id = validated_data.pop('user_id')
        user = User.objects.get(id=user_id)
        validated_data['user'] = user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update EventMembership with proper user_id handling"""
        if 'user_id' in validated_data:
            user_id = validated_data.pop('user_id')
            user = User.objects.get(id=user_id)
            validated_data['user'] = user
        return super().update(instance, validated_data)


class BatchMembershipSerializer(serializers.ModelSerializer):
    membership = EventMembershipSerializer(read_only=True)
    membership_id = serializers.IntegerField(write_only=True)
    batch_id = serializers.IntegerField(write_only=True, required=False)  # Accept batch_id from UI
    batch = serializers.PrimaryKeyRelatedField(queryset=Batch.objects.all(), required=False)  # Make batch not required when batch_id is provided
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    user_name = serializers.CharField(source='membership.user.username', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.username', read_only=True)
    
    class Meta:
        model = BatchMembership
        fields = [
            'id', 'batch', 'batch_id', 'batch_number', 'membership', 'membership_id',
            'user_name', 'can_activate', 'can_verify', 'assigned_by',
            'assigned_by_name', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_membership_id(self, value):
        """Validate that the membership exists"""
        try:
            EventMembership.objects.get(id=value)
            return value
        except EventMembership.DoesNotExist:
            raise serializers.ValidationError("Event membership does not exist")
    
    def validate(self, attrs):
        """Validate batch membership constraints"""
        membership_id = attrs.get('membership_id')
        batch = attrs.get('batch')
        batch_id = attrs.get('batch_id')
        
        # Ensure either batch or batch_id is provided
        if not batch and not batch_id:
            raise serializers.ValidationError("Either 'batch' or 'batch_id' must be provided")
        
        # Get batch object if batch_id is provided
        if batch_id and not batch:
            try:
                batch = Batch.objects.get(id=batch_id)
            except Batch.DoesNotExist:
                raise serializers.ValidationError("Batch does not exist")
        
        if membership_id and batch:
            membership = EventMembership.objects.filter(id=membership_id).select_related('event').first()
            if membership and membership.event_id != batch.event_id:
                raise serializers.ValidationError("Membership must be for the same event as the batch")
            # Check for existing batch membership
            if BatchMembership.objects.filter(membership_id=membership_id, batch=batch).exists():
                raise serializers.ValidationError("User is already assigned to this batch")
        
        return attrs
    
    def create(self, validated_data):
        """Create BatchMembership with proper membership_id and batch_id handling"""
        membership_id = validated_data.pop('membership_id')
        membership = EventMembership.objects.get(id=membership_id)
        validated_data['membership'] = membership
        
        # Handle batch_id if provided instead of batch
        if 'batch_id' in validated_data:
            from .models import Batch
            batch_id = validated_data.pop('batch_id')
            batch = Batch.objects.get(id=batch_id)
            validated_data['batch'] = batch
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update BatchMembership with proper membership_id and batch_id handling"""
        if 'membership_id' in validated_data:
            membership_id = validated_data.pop('membership_id')
            membership = EventMembership.objects.get(id=membership_id)
            validated_data['membership'] = membership
        
        # Handle batch_id if provided instead of batch
        if 'batch_id' in validated_data:
            from .models import Batch
            batch_id = validated_data.pop('batch_id')
            batch = Batch.objects.get(id=batch_id)
            validated_data['batch'] = batch
            
        return super().update(instance, validated_data)
