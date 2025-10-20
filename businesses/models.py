from django.db import models
from django.utils import timezone
from decimal import Decimal
from core.models import BaseModel


# ============================================================================
# PHASE 1: CORE BUSINESS ENTITY
# ============================================================================


class SaccoEnterprise(BaseModel):
    """
    A business venture owned/managed by a SACCO.
    Examples: shop, restaurant, farm, transport service
    
    Phase 1: Business Module - Core Entity
    """
    sacco = models.ForeignKey(
        'saccos.SaccoOrganization',
        on_delete=models.CASCADE,
        related_name='enterprises'
    )
    
    # Basic Information
    name = models.CharField(max_length=200)
    business_type = models.CharField(
        max_length=50,
        choices=[
            ('retail', 'Retail Shop'),
            ('wholesale', 'Wholesale'),
            ('restaurant', 'Restaurant/Café'),
            ('farm', 'Agriculture'),
            ('transport', 'Transport Service'),
            ('manufacturing', 'Manufacturing'),
            ('services', 'Services'),
            ('other', 'Other'),
        ],
        default='retail'
    )
    description = models.TextField(blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    
    # Finance Integration
    finance_account = models.ForeignKey(
        'finance.Account',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='enterprises',
        help_text="Main operating account for this business"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Management
    managed_by = models.ManyToManyField(
        'users.User',
        related_name='managed_enterprises',
        blank=True
    )
    
    class Meta:
        db_table = 'businesses_enterprise'
        verbose_name = 'SACCO Enterprise'
        verbose_name_plural = 'SACCO Enterprises'
        ordering = ['-created_at']
        unique_together = [['sacco', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.sacco.name})"


class EnterpriseConfiguration(BaseModel):
    """
    Configuration for which features are enabled for this business.
    Controls module availability and integration behavior.
    
    Phase 1: Business Module - Feature Configuration
    """
    enterprise = models.OneToOneField(
        SaccoEnterprise,
        on_delete=models.CASCADE,
        related_name='configuration'
    )
    
    # Module Toggles
    stock_management_enabled = models.BooleanField(
        default=False,
        help_text="Enable inventory/stock tracking"
    )
    sales_management_enabled = models.BooleanField(
        default=False,
        help_text="Enable sales/POS features"
    )
    
    # Integration Settings
    auto_create_finance_entries = models.BooleanField(
        default=True,
        help_text="Automatically create finance transactions for business activities"
    )
    sales_affect_stock = models.BooleanField(
        default=True,
        help_text="Sales automatically reduce stock (requires both stock and sales modules)"
    )
    
    # Business Settings
    default_currency = models.CharField(max_length=3, default='UGX')
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Default tax rate percentage"
    )
    
    # Additional Settings (JSON for flexibility)
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional configuration as JSON"
    )
    
    class Meta:
        db_table = 'businesses_configuration'
        verbose_name = 'Enterprise Configuration'
        verbose_name_plural = 'Enterprise Configurations'
    
    def __str__(self):
        return f"Config for {self.enterprise.name}"


# ============================================================================
# PHASE 2: STOCK MANAGEMENT MODULE
# ============================================================================


class StockItem(BaseModel):
    """
    A product or inventory item that can be bought/sold.
    Phase 2: Stock Management
    """
    enterprise = models.ForeignKey(
        SaccoEnterprise,
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    
    # Product Information
    sku = models.CharField(
        max_length=50,
        blank=True,
        help_text="Stock keeping unit - unique identifier"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    
    # Pricing
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit (what we pay)"
    )
    selling_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Selling price per unit"
    )
    
    # Inventory
    quantity_on_hand = models.IntegerField(
        default=0,
        help_text="Current stock level"
    )
    reorder_level = models.IntegerField(
        default=0,
        help_text="Alert when stock falls below this level"
    )
    reorder_quantity = models.IntegerField(
        default=0,
        help_text="Suggested reorder quantity"
    )
    
    # Settings
    unit_of_measure = models.CharField(
        max_length=20,
        default='piece',
        help_text="Unit of measure (piece, kg, liter, etc.)"
    )
    barcode = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'businesses_stock_item'
        ordering = ['name']
        indexes = [
            models.Index(fields=['enterprise', 'is_active']),
            models.Index(fields=['enterprise', 'category']),
            models.Index(fields=['enterprise', 'sku']),
        ]
    
    def __str__(self):
        return f"{self.name} (QOH: {self.quantity_on_hand})"
    
    @property
    def is_low_stock(self):
        """Check if stock is below reorder level"""
        return self.quantity_on_hand <= self.reorder_level
    
    @property
    def total_value(self):
        """Calculate total inventory value at cost"""
        if self.cost_price is None:
            return Decimal('0')
        return self.quantity_on_hand * self.cost_price
    
    @property
    def potential_revenue(self):
        """Calculate potential revenue if all sold"""
        if self.selling_price is None:
            return Decimal('0')
        return self.quantity_on_hand * self.selling_price
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.selling_price is None or self.cost_price is None:
            return Decimal('0')
        if self.selling_price == 0:
            return Decimal('0')
        return ((self.selling_price - self.cost_price) / self.selling_price) * 100


class StockMovement(BaseModel):
    """
    Immutable log of all stock changes.
    Every change to stock must create a movement record.
    Phase 2: Stock Management
    """
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    
    movement_type = models.CharField(
        max_length=20,
        choices=[
            ('IN', 'Stock In'),
            ('OUT', 'Stock Out'),
            ('ADJUSTMENT', 'Adjustment'),
            ('DAMAGE', 'Damaged/Lost'),
            ('RETURN', 'Customer Return'),
        ]
    )
    
    # Quantity (positive for IN, negative for OUT)
    quantity = models.IntegerField(
        help_text="Positive for stock in, negative for stock out"
    )
    
    # Cost at time of movement
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="Cost per unit at time of movement"
    )
    
    # Context
    movement_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Tracking
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='stock_movements'
    )
    
    # Link to source transaction (optional - for later integration)
    source_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Source type: sale, purchase, adjustment, etc."
    )
    source_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of source record"
    )
    
    class Meta:
        db_table = 'businesses_stock_movement'
        ordering = ['-movement_date', '-created_at']
        indexes = [
            models.Index(fields=['stock_item', 'movement_date']),
            models.Index(fields=['movement_type', 'movement_date']),
        ]
    
    def __str__(self):
        return f"{self.movement_type} {abs(self.quantity)} x {self.stock_item.name}"
    
    @property
    def total_value(self):
        """Calculate total value of this movement"""
        return abs(self.quantity) * self.unit_cost


# ============================================================================
# PHASE 3: SALES MANAGEMENT MODULE
# ============================================================================


class Sale(BaseModel):
    """
    A sales transaction.
    Phase 3: Sales Management
    """
    enterprise = models.ForeignKey(
        SaccoEnterprise,
        on_delete=models.CASCADE,
        related_name='sales'
    )
    
    # Sale Information
    sale_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Auto-generated unique sale number"
    )
    sale_date = models.DateField()
    
    # Customer (optional for now)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Sum of all line items before tax/discount"
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total tax amount"
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total discount"
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Final amount after tax and discount"
    )
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('mobile', 'Mobile Money'),
            ('bank', 'Bank Transfer'),
            ('credit', 'Credit'),
        ],
        default='cash'
    )
    amount_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Amount received from customer"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft'
    )
    
    # Tracking
    served_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='sales_made'
    )
    notes = models.TextField(blank=True)
    
    # Finance Integration (for Phase 4)
    finance_transaction = models.ForeignKey(
        'finance.Transaction',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='business_sales',
        help_text="Linked finance transaction"
    )
    
    class Meta:
        db_table = 'businesses_sale'
        ordering = ['-sale_date', '-created_at']
        indexes = [
            models.Index(fields=['enterprise', 'sale_date']),
            models.Index(fields=['enterprise', 'status']),
            models.Index(fields=['sale_date']),
        ]
    
    def __str__(self):
        return f"Sale #{self.sale_number} - {self.total_amount}"
    
    def generate_sale_number(self):
        """Auto-generate unique sale number"""
        from django.utils import timezone
        
        today = timezone.now().date()
        prefix = f"S{today.strftime('%Y%m%d')}"
        
        # Find last sale with this prefix
        last_sale = Sale.objects.filter(
            sale_number__startswith=prefix
        ).order_by('-sale_number').first()
        
        if last_sale:
            # Extract sequence number and increment
            last_num = int(last_sale.sale_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:04d}"
    
    @property
    def change_amount(self):
        """Calculate change to give customer"""
        if self.amount_paid is None or self.total_amount is None:
            return Decimal('0')
        return self.amount_paid - self.total_amount
    
    @property
    def total_cost(self):
        """Calculate total cost of items sold"""
        return sum(item.total_cost for item in self.items.all()) or Decimal('0')
    
    @property
    def profit(self):
        """Calculate profit on this sale"""
        if self.total_amount is None:
            return Decimal('0')
        return self.total_amount - self.total_cost


class SaleItem(BaseModel):
    """
    Line items in a sale.
    Phase 3: Sales Management
    """
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items'
    )
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.PROTECT,
        related_name='sale_items'
    )
    
    # Quantity and Pricing
    quantity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Quantity sold"
    )
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Selling price per unit"
    )
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Cost per unit (for profit calculation)"
    )
    
    # Discounts
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Discount percentage"
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Discount amount"
    )
    
    # Tax
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Tax rate percentage"
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Tax amount"
    )
    
    # Totals
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="quantity × unit_price"
    )
    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Final amount after discount and tax"
    )
    
    class Meta:
        db_table = 'businesses_sale_item'
        ordering = ['id']
    
    def __str__(self):
        quantity = self.quantity if self.quantity is not None else 0
        stock_name = self.stock_item.name if self.stock_item else "Unknown Item"
        return f"{quantity} × {stock_name}"
    
    @property
    def total_cost(self):
        """Calculate total cost for this line item"""
        if self.quantity is None or self.unit_cost is None:
            return Decimal('0')
        return self.quantity * self.unit_cost
    
    @property
    def profit(self):
        """Calculate profit on this line item"""
        if self.total is None:
            return Decimal('0')
        return self.total - self.total_cost
