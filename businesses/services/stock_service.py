from django.db import transaction
from django.db.models import Sum, F, Value, DecimalField, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from businesses.models import StockItem, StockMovement


class StockService:
    """
    All stock operations go through this service.
    Ensures quantity_on_hand stays in sync with movements.
    Phase 2: Stock Management
    """
    
    @staticmethod
    @transaction.atomic
    def receive_stock(stock_item, quantity, unit_cost, user, notes='', date=None, reference=''):
        """
        Record stock coming in (purchase, return, etc.)
        
        Args:
            stock_item: StockItem instance
            quantity: Amount received (must be positive)
            unit_cost: Cost per unit
            user: User recording the movement
            notes: Optional notes
            date: Movement date (defaults to today)
            reference: Reference number (PO, invoice, etc.)
        
        Returns:
            StockMovement instance
        
        Raises:
            ValueError: If quantity is not positive
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive for stock receipt")
        
        # Create movement record
        movement = StockMovement.objects.create(
            stock_item=stock_item,
            movement_type='IN',
            quantity=quantity,  # Positive
            unit_cost=unit_cost,
            movement_date=date or timezone.now().date(),
            reference_number=reference,
            notes=notes,
            recorded_by=user
        )
        
        # Update stock item
        stock_item.quantity_on_hand += quantity
        stock_item.cost_price = unit_cost  # Update to latest cost
        stock_item.save(update_fields=['quantity_on_hand', 'cost_price', 'updated_at'])
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def issue_stock(stock_item, quantity, user, notes='', date=None, reference='', source_type='', source_id=None):
        """
        Remove stock (sale, damage, etc.)
        
        Args:
            stock_item: StockItem instance
            quantity: Amount to remove (must be positive)
            user: User recording the movement
            notes: Optional notes
            date: Movement date (defaults to today)
            reference: Reference number
            source_type: Type of source (sale, damage, etc.)
            source_id: ID of source record
        
        Returns:
            StockMovement instance
        
        Raises:
            ValueError: If quantity invalid or insufficient stock
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive for stock issue")
        
        if stock_item.quantity_on_hand < quantity:
            raise ValueError(
                f"Insufficient stock for {stock_item.name}. "
                f"Available: {stock_item.quantity_on_hand}, "
                f"Requested: {quantity}"
            )
        
        # Create movement record (negative quantity)
        movement = StockMovement.objects.create(
            stock_item=stock_item,
            movement_type='OUT',
            quantity=-quantity,  # Negative for OUT
            unit_cost=stock_item.cost_price or Decimal('0'),
            movement_date=date or timezone.now().date(),
            reference_number=reference,
            notes=notes,
            recorded_by=user,
            source_type=source_type,
            source_id=source_id
        )
        
        # Update stock item
        stock_item.quantity_on_hand -= quantity
        stock_item.save(update_fields=['quantity_on_hand', 'updated_at'])
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def adjust_stock(stock_item, new_quantity, reason, user, date=None):
        """
        Manual stock correction (for mistakes, physical counts, etc.)
        
        Args:
            stock_item: StockItem instance
            new_quantity: New quantity after adjustment
            reason: Reason for adjustment (required)
            user: User making the adjustment
            date: Adjustment date (defaults to today)
        
        Returns:
            StockMovement instance
        
        Raises:
            ValueError: If new_quantity is negative or reason is empty
        """
        if new_quantity < 0:
            raise ValueError("New quantity cannot be negative")
        
        if not reason or reason.strip() == '':
            raise ValueError("Reason is required for stock adjustments")
        
        # Calculate difference
        difference = new_quantity - stock_item.quantity_on_hand
        
        if difference == 0:
            raise ValueError("New quantity is same as current quantity. No adjustment needed.")
        
        # Create movement record
        movement = StockMovement.objects.create(
            stock_item=stock_item,
            movement_type='ADJUSTMENT',
            quantity=difference,  # Can be positive or negative
            unit_cost=stock_item.cost_price or Decimal('0'),
            movement_date=date or timezone.now().date(),
            notes=f"Adjustment: {reason}. Old quantity: {stock_item.quantity_on_hand}, New quantity: {new_quantity}",
            recorded_by=user
        )
        
        # Update stock item
        stock_item.quantity_on_hand = new_quantity
        stock_item.save(update_fields=['quantity_on_hand', 'updated_at'])
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def record_damage(stock_item, quantity, reason, user, date=None):
        """
        Record damaged or lost stock
        
        Args:
            stock_item: StockItem instance
            quantity: Amount damaged/lost
            reason: Reason/description
            user: User recording
            date: Date of damage
        
        Returns:
            StockMovement instance
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if stock_item.quantity_on_hand < quantity:
            raise ValueError(
                f"Cannot record damage exceeding available stock. "
                f"Available: {stock_item.quantity_on_hand}, "
                f"Damage: {quantity}"
            )
        
        movement = StockMovement.objects.create(
            stock_item=stock_item,
            movement_type='DAMAGE',
            quantity=-quantity,  # Negative
            unit_cost=stock_item.cost_price or Decimal('0'),
            movement_date=date or timezone.now().date(),
            notes=f"Damage/Loss: {reason}",
            recorded_by=user
        )
        
        # Update stock
        stock_item.quantity_on_hand -= quantity
        stock_item.save(update_fields=['quantity_on_hand', 'updated_at'])
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def record_return(stock_item, quantity, notes, user, date=None):
        """
        Record customer return (adds stock back)
        
        Args:
            stock_item: StockItem instance
            quantity: Amount returned
            notes: Notes about the return
            user: User recording
            date: Return date
        
        Returns:
            StockMovement instance
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        movement = StockMovement.objects.create(
            stock_item=stock_item,
            movement_type='RETURN',
            quantity=quantity,  # Positive (adds stock)
            unit_cost=stock_item.cost_price or Decimal('0'),
            movement_date=date or timezone.now().date(),
            notes=f"Customer return: {notes}",
            recorded_by=user
        )
        
        # Update stock
        stock_item.quantity_on_hand += quantity
        stock_item.save(update_fields=['quantity_on_hand', 'updated_at'])
        
        return movement
    
    # Query methods
    
    @staticmethod
    def get_stock_value(enterprise):
        """
        Calculate total inventory value at cost for an enterprise
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            Decimal: Total inventory value
        """
        total = StockItem.objects.filter(
            enterprise=enterprise,
            is_active=True
        ).aggregate(
            total=Sum(F('quantity_on_hand') * Coalesce(F('cost_price'), Value(0, output_field=DecimalField())))
        )['total']
        
        return total or Decimal('0')
    
    @staticmethod
    def get_potential_revenue(enterprise):
        """
        Calculate potential revenue if all stock sold at selling price
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            Decimal: Potential revenue
        """
        total = StockItem.objects.filter(
            enterprise=enterprise,
            is_active=True
        ).aggregate(
            total=Sum(F('quantity_on_hand') * Coalesce(F('selling_price'), Value(0, output_field=DecimalField())))
        )['total']
        
        return total or Decimal('0')
    
    @staticmethod
    def get_low_stock_items(enterprise):
        """
        Get items that need reordering
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            QuerySet of StockItem instances below reorder level
        """
        return StockItem.objects.filter(
            enterprise=enterprise,
            is_active=True,
            quantity_on_hand__lte=F('reorder_level')
        ).order_by('quantity_on_hand')
    
    @staticmethod
    def get_stock_movement_history(stock_item, start_date=None, end_date=None):
        """
        Get movement history for a stock item
        
        Args:
            stock_item: StockItem instance
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            QuerySet of StockMovement instances
        """
        movements = StockMovement.objects.filter(stock_item=stock_item)
        
        if start_date:
            movements = movements.filter(movement_date__gte=start_date)
        
        if end_date:
            movements = movements.filter(movement_date__lte=end_date)
        
        return movements.select_related('recorded_by').order_by('-movement_date', '-created_at')
    
    @staticmethod
    def get_stock_summary(enterprise):
        """
        Get summary statistics for enterprise stock
        
        Args:
            enterprise: SaccoEnterprise instance
        
        Returns:
            dict with summary data
        """
        items = StockItem.objects.filter(enterprise=enterprise, is_active=True)
        
        summary = items.aggregate(
            total_items=Count('id'),
            total_value=Sum(F('quantity_on_hand') * Coalesce(F('cost_price'), Value(0, output_field=DecimalField()))),
            total_potential_revenue=Sum(F('quantity_on_hand') * Coalesce(F('selling_price'), Value(0, output_field=DecimalField())))
        )
        
        low_stock_count = StockItem.objects.filter(
            enterprise=enterprise,
            is_active=True,
            quantity_on_hand__lte=F('reorder_level')
        ).count()
        
        out_of_stock_count = StockItem.objects.filter(
            enterprise=enterprise,
            is_active=True,
            quantity_on_hand=0
        ).count()
        
        return {
            'total_items': summary['total_items'] or 0,
            'total_value': summary['total_value'] or Decimal('0'),
            'potential_revenue': summary['total_potential_revenue'] or Decimal('0'),
            'potential_profit': (summary['total_potential_revenue'] or Decimal('0')) - (summary['total_value'] or Decimal('0')),
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count
        }


# Import Count for summary
from django.db.models import Count
