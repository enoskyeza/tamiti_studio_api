from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Event, EventManager, BatchManager, TicketType, Batch, Ticket, ScanLog, BatchExport


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'name']
    
    def get_name(self, obj):
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username


class EventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'date', 'venue', 'status',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'stats'
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
            'voided_tickets': voided_tickets
        }


class EventManagerSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    added_by_name = serializers.CharField(source='assigned_by.username', read_only=True)
    
    class Meta:
        model = EventManager
        fields = [
            'id', 'user', 'user_name', 'user_email', 'role', 'permissions',
            'assigned_by', 'added_by_name', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'assigned_by', 'created_at']


class EventManagerCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=EventManager.ROLE_CHOICES, default='manager')
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )


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
    
    class Meta:
        model = Batch
        fields = [
            'id', 'batch_number', 'event', 'event_name', 'quantity',
            'activated_count', 'scanned_count', 'voided_count', 'unused_count',
            'status', 'created_by', 'created_by_name', 'created_at',
            'voided_at', 'voided_by', 'void_reason', 'layout'
        ]
        read_only_fields = [
            'id', 'batch_number', 'activated_count', 'scanned_count',
            'voided_count', 'unused_count', 'created_by', 'created_at'
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


class BuyerInfoSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    ticket_type_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class TicketSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    event_name = serializers.CharField(source='batch.event.name', read_only=True)
    activated_by_name = serializers.CharField(source='activated_by.username', read_only=True)
    scanned_by_name = serializers.CharField(source='scanned_by.username', read_only=True)
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)
    buyer_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'batch', 'batch_number', 'event_name', 'short_code', 'qr_code',
            'status', 'buyer_name', 'buyer_phone', 'buyer_email', 'ticket_type',
            'ticket_type_name', 'notes', 'activated_at', 'activated_by',
            'activated_by_name', 'scanned_at', 'scanned_by', 'scanned_by_name',
            'gate', 'created_at', 'buyer_info'
        ]
        read_only_fields = [
            'id', 'short_code', 'qr_code', 'activated_at', 'activated_by',
            'scanned_at', 'scanned_by', 'created_at'
        ]
    
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


class BatchManagerSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    manager_name = serializers.CharField(source='manager.user.username', read_only=True)
    manager_email = serializers.CharField(source='manager.user.email', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.username', read_only=True)
    
    class Meta:
        model = BatchManager
        fields = [
            'id', 'batch', 'batch_number', 'manager', 'manager_name', 'manager_email',
            'can_activate', 'can_verify', 'assigned_by', 'assigned_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'assigned_by', 'created_at']


class BatchManagerCreateSerializer(serializers.Serializer):
    batch_id = serializers.IntegerField()
    manager_id = serializers.IntegerField()
    can_activate = serializers.BooleanField(default=True)
    can_verify = serializers.BooleanField(default=True)
