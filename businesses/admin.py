from django.contrib import admin
from .models import (
    SaccoEnterprise, EnterpriseConfiguration,
    StockItem, StockMovement,
    Sale, SaleItem
)
from .services.business_service import BusinessService


@admin.register(SaccoEnterprise)
class SaccoEnterpriseAdmin(admin.ModelAdmin):
    list_display = ['name', 'sacco', 'business_type', 'is_active', 'created_at']
    list_filter = ['business_type', 'is_active', 'sacco']
    search_fields = ['name', 'description', 'sacco__name']
    filter_horizontal = ['managed_by']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sacco', 'name', 'business_type', 'description')
        }),
        ('Contact Details', {
            'fields': ('phone', 'email', 'location')
        }),
        ('Finance Integration', {
            'fields': ('finance_account',)
        }),
        ('Management', {
            'fields': ('managed_by', 'is_active')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-create configuration and finance accounts for new businesses"""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        if is_new:
            # Create configuration if it doesn't exist
            if not hasattr(obj, 'configuration'):
                EnterpriseConfiguration.objects.create(enterprise=obj)
            
            # Setup finance accounts if not already set up
            if not obj.finance_account:
                BusinessService.setup_finance_accounts(obj)


@admin.register(EnterpriseConfiguration)
class EnterpriseConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'enterprise', 
        'stock_management_enabled', 
        'sales_management_enabled',
        'auto_create_finance_entries'
    ]
    list_filter = [
        'stock_management_enabled',
        'sales_management_enabled',
        'auto_create_finance_entries',
        'sales_affect_stock'
    ]
    search_fields = ['enterprise__name']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Enterprise', {
            'fields': ('enterprise',)
        }),
        ('Module Toggles', {
            'fields': ('stock_management_enabled', 'sales_management_enabled')
        }),
        ('Integration Settings', {
            'fields': ('auto_create_finance_entries', 'sales_affect_stock')
        }),
        ('Business Settings', {
            'fields': ('default_currency', 'tax_rate')
        }),
        ('Advanced Settings', {
            'fields': ('settings',),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# PHASE 2: STOCK MANAGEMENT ADMIN
# ============================================================================


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'enterprise', 'sku', 'quantity_on_hand', 
        'cost_price', 'selling_price', 'is_low_stock', 'is_active'
    ]
    list_filter = ['enterprise', 'category', 'is_active']
    search_fields = ['name', 'sku', 'description', 'barcode']
    readonly_fields = ['uuid', 'created_at', 'updated_at', 'total_value', 'profit_margin']
    
    fieldsets = (
        ('Enterprise', {
            'fields': ('enterprise',)
        }),
        ('Product Information', {
            'fields': ('sku', 'name', 'description', 'category', 'barcode')
        }),
        ('Pricing', {
            'fields': ('cost_price', 'selling_price', 'profit_margin')
        }),
        ('Inventory', {
            'fields': ('quantity_on_hand', 'reorder_level', 'reorder_quantity', 'unit_of_measure')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('System', {
            'fields': ('uuid', 'total_value', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        'stock_item', 'movement_type', 'quantity', 
        'unit_cost', 'movement_date', 'recorded_by'
    ]
    list_filter = ['movement_type', 'movement_date', 'stock_item__enterprise']
    search_fields = ['stock_item__name', 'reference_number', 'notes']
    readonly_fields = [
        'uuid', 'stock_item', 'movement_type', 'quantity', 
        'unit_cost', 'movement_date', 'recorded_by', 
        'reference_number', 'notes', 'total_value',
        'source_type', 'source_id', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'movement_date'
    
    fieldsets = (
        ('Movement Details', {
            'fields': ('stock_item', 'movement_type', 'quantity', 'unit_cost', 'total_value')
        }),
        ('Context', {
            'fields': ('movement_date', 'reference_number', 'notes')
        }),
        ('Source', {
            'fields': ('source_type', 'source_id')
        }),
        ('Tracking', {
            'fields': ('recorded_by',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Don't allow manual creation - use StockService
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion - audit trail
        return False


# ============================================================================
# PHASE 3: SALES MANAGEMENT ADMIN
# ============================================================================


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['stock_item', 'quantity', 'unit_price', 'unit_cost', 'subtotal', 'total', 'total_cost', 'profit']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = [
        'sale_number', 'enterprise', 'sale_date',
        'total_amount', 'status', 'payment_method', 'served_by'
    ]
    list_filter = ['status', 'payment_method', 'sale_date', 'enterprise']
    search_fields = ['sale_number', 'customer_name', 'customer_phone']
    readonly_fields = [
        'uuid', 'sale_number', 'change_amount', 'total_cost', 'profit',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'sale_date'
    inlines = [SaleItemInline]
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('enterprise', 'sale_number', 'sale_date', 'status')
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_phone')
        }),
        ('Amounts', {
            'fields': (
                'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
                'total_cost', 'profit'
            )
        }),
        ('Payment', {
            'fields': ('payment_method', 'amount_paid', 'change_amount')
        }),
        ('Tracking', {
            'fields': ('served_by', 'notes')
        }),
        ('Finance', {
            'fields': ('finance_transaction',),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = [
        'sale', 'stock_item', 'quantity',
        'unit_price', 'discount_amount', 'total', 'profit'
    ]
    list_filter = ['sale__enterprise', 'sale__sale_date']
    search_fields = ['sale__sale_number', 'stock_item__name']
    readonly_fields = ['uuid', 'total_cost', 'profit', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Sale', {
            'fields': ('sale',)
        }),
        ('Item', {
            'fields': ('stock_item', 'quantity')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'unit_cost', 'total_cost', 'profit')
        }),
        ('Discounts & Tax', {
            'fields': ('discount_percentage', 'discount_amount', 'tax_rate', 'tax_amount')
        }),
        ('Totals', {
            'fields': ('subtotal', 'total')
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
