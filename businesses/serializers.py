from rest_framework import serializers
from .models import (
    SaccoEnterprise, EnterpriseConfiguration,
    StockItem, StockMovement,
    Sale, SaleItem
)


class EnterpriseConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for Enterprise Configuration"""
    
    class Meta:
        model = EnterpriseConfiguration
        fields = [
            'id', 'uuid',
            'stock_management_enabled',
            'sales_management_enabled',
            'auto_create_finance_entries',
            'sales_affect_stock',
            'default_currency',
            'tax_rate',
            'settings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class SaccoEnterpriseSerializer(serializers.ModelSerializer):
    """Serializer for SACCO Enterprise"""
    configuration = EnterpriseConfigurationSerializer(read_only=True)
    sacco_name = serializers.CharField(source='sacco.name', read_only=True)
    finance_account_name = serializers.CharField(
        source='finance_account.name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = SaccoEnterprise
        fields = [
            'id', 'uuid', 'name', 'business_type', 'description',
            'phone', 'email', 'location',
            'sacco', 'sacco_name',
            'finance_account', 'finance_account_name',
            'is_active',
            'configuration',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'sacco_name', 'finance_account_name',
            'configuration', 'created_at', 'updated_at'
        ]


class SaccoEnterpriseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new enterprise"""
    
    class Meta:
        model = SaccoEnterprise
        fields = [
            'name', 'business_type', 'description',
            'phone', 'email', 'location', 'sacco'
        ]
    
    def create(self, validated_data):
        """Use BusinessService to create with proper setup"""
        from .services.business_service import BusinessService
        
        enterprise = BusinessService.create_business(
            sacco=validated_data['sacco'],
            name=validated_data['name'],
            business_type=validated_data['business_type'],
            description=validated_data.get('description', ''),
            phone=validated_data.get('phone', ''),
            email=validated_data.get('email', ''),
            location=validated_data.get('location', ''),
        )
        
        return enterprise


# ============================================================================
# PHASE 2: STOCK MANAGEMENT SERIALIZERS
# ============================================================================


class StockItemSerializer(serializers.ModelSerializer):
    """Serializer for Stock Item"""
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True)
    is_low_stock = serializers.ReadOnlyField()
    total_value = serializers.ReadOnlyField()
    potential_revenue = serializers.ReadOnlyField()
    profit_margin = serializers.ReadOnlyField()
    # Pack pricing calculated fields
    is_pack_item = serializers.ReadOnlyField()
    unit_cost_from_pack = serializers.ReadOnlyField()
    pack_revenue = serializers.ReadOnlyField()
    pack_profit = serializers.ReadOnlyField()
    pack_profit_margin = serializers.ReadOnlyField()
    
    class Meta:
        model = StockItem
        fields = [
            'id', 'uuid', 'enterprise', 'enterprise_name',
            'sku', 'name', 'description', 'category',
            # Unit pricing
            'cost_price', 'selling_price',
            # Pack/Bulk pricing
            'pack_size', 'pack_cost_price', 'pack_selling_price',
            # Inventory
            'quantity_on_hand', 'reorder_level', 'reorder_quantity',
            'unit_of_measure', 'barcode', 'is_active',
            # Calculated fields
            'is_low_stock', 'total_value', 'potential_revenue', 'profit_margin',
            'is_pack_item', 'unit_cost_from_pack', 'pack_revenue', 'pack_profit', 'pack_profit_margin',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'enterprise_name', 'is_low_stock', 'total_value',
            'potential_revenue', 'profit_margin',
            'is_pack_item', 'unit_cost_from_pack', 'pack_revenue', 'pack_profit', 'pack_profit_margin',
            'created_at', 'updated_at'
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for Stock Movement"""
    stock_item_name = serializers.CharField(source='stock_item.name', read_only=True)
    stock_item_sku = serializers.CharField(source='stock_item.sku', read_only=True)
    recorded_by_name = serializers.CharField(
        source='recorded_by.get_full_name',
        read_only=True
    )
    total_value = serializers.ReadOnlyField()
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'uuid', 'stock_item', 'stock_item_name', 'stock_item_sku',
            'movement_type', 'quantity', 'unit_cost',
            'movement_date', 'reference_number', 'notes',
            'recorded_by', 'recorded_by_name',
            'source_type', 'source_id',
            'total_value',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'stock_item_name', 'stock_item_sku',
            'recorded_by_name', 'total_value',
            'created_at', 'updated_at'
        ]


# ============================================================================
# PHASE 3: SALES MANAGEMENT SERIALIZERS
# ============================================================================


class SaleItemSerializer(serializers.ModelSerializer):
    """Serializer for Sale Item (line item)"""
    stock_item_name = serializers.CharField(source='stock_item.name', read_only=True)
    stock_item_sku = serializers.CharField(source='stock_item.sku', read_only=True)
    total_cost = serializers.ReadOnlyField()
    profit = serializers.ReadOnlyField()
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'uuid', 'sale', 'stock_item', 'stock_item_name', 'stock_item_sku',
            'quantity', 'unit_price', 'unit_cost',
            'discount_percentage', 'discount_amount',
            'tax_rate', 'tax_amount',
            'subtotal', 'total',
            'total_cost', 'profit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'stock_item_name', 'stock_item_sku',
            'total_cost', 'profit', 'created_at', 'updated_at'
        ]


class SaleSerializer(serializers.ModelSerializer):
    """Serializer for Sale"""
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True)
    served_by_name = serializers.CharField(source='served_by.get_full_name', read_only=True)
    items = SaleItemSerializer(many=True, read_only=True)
    change_amount = serializers.ReadOnlyField()
    total_cost = serializers.ReadOnlyField()
    profit = serializers.ReadOnlyField()
    
    class Meta:
        model = Sale
        fields = [
            'id', 'uuid', 'enterprise', 'enterprise_name',
            'sale_number', 'sale_date',
            'customer_name', 'customer_phone',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'payment_method', 'amount_paid', 'change_amount',
            'status', 'served_by', 'served_by_name', 'notes',
            'items', 'total_cost', 'profit',
            'finance_transaction',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'uuid', 'enterprise_name', 'served_by_name',
            'sale_number', 'change_amount', 'total_cost', 'profit',
            'items', 'created_at', 'updated_at'
        ]


class SaleCreateSerializer(serializers.Serializer):
    """Serializer for creating a sale with items"""
    enterprise = serializers.PrimaryKeyRelatedField(
        queryset=SaccoEnterprise.objects.all()
    )
    customer_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=['cash', 'mobile', 'bank', 'credit'],
        default='cash'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    items = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of items with stock_item_id, quantity, optional unit_price and discount"
    )
    
    def create(self, validated_data):
        """Use SalesService to create sale"""
        from .services.sales_service import SalesService
        
        user = self.context['request'].user
        
        sale = SalesService.create_sale(
            enterprise=validated_data['enterprise'],
            items_data=validated_data['items'],
            user=user,
            customer_name=validated_data.get('customer_name', ''),
            customer_phone=validated_data.get('customer_phone', ''),
            payment_method=validated_data.get('payment_method', 'cash'),
            notes=validated_data.get('notes', '')
        )
        
        return sale
