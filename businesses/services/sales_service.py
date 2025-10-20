from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from businesses.models import Sale, SaleItem, StockItem
from businesses.services.stock_service import StockService


class SalesService:
    """
    All sales operations go through this service.
    Handles sale creation, completion, and integration with stock.
    Phase 3: Sales Management
    """
    
    @staticmethod
    @transaction.atomic
    def create_sale(enterprise, items_data, user, customer_name='', customer_phone='', payment_method='cash', notes=''):
        """
        Create a new sale with items.
        
        Args:
            enterprise: SaccoEnterprise instance
            items_data: List of dicts with item details
                [
                    {
                        'stock_item_id': 1,
                        'quantity': 2,
                        'unit_price': 10000,  # optional, defaults to item.selling_price
                        'discount': 0         # optional
                    }
                ]
            user: User creating the sale
            customer_name: Optional customer name
            customer_phone: Optional customer phone
            payment_method: Payment method (cash, mobile, bank, credit)
            notes: Optional notes
        
        Returns:
            Sale instance
        
        Raises:
            ValueError: If items_data is empty or invalid
        """
        if not items_data or len(items_data) == 0:
            raise ValueError("Sale must have at least one item")
        
        # Create sale (draft status)
        sale = Sale.objects.create(
            enterprise=enterprise,
            sale_date=timezone.now().date(),
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            served_by=user,
            notes=notes,
            status='draft'
        )
        
        # Generate sale number
        sale.sale_number = sale.generate_sale_number()
        sale.save(update_fields=['sale_number'])
        
        # Add items and calculate totals
        subtotal = Decimal('0')
        total_discount = Decimal('0')
        total_tax = Decimal('0')
        
        for item_data in items_data:
            stock_item = StockItem.objects.get(id=item_data['stock_item_id'])
            quantity = int(item_data['quantity'])
            
            if quantity <= 0:
                raise ValueError(f"Quantity must be positive for {stock_item.name}")
            
            # Price per unit (use provided or default to selling_price)
            if 'unit_price' in item_data:
                unit_price = Decimal(str(item_data['unit_price']))
            elif stock_item.selling_price is not None:
                unit_price = stock_item.selling_price
            else:
                raise ValueError(f"No selling price set for {stock_item.name}. Please set a price or provide unit_price.")
            
            # Calculate line subtotal
            line_subtotal = quantity * unit_price
            
            # Discount
            discount_amount = Decimal(str(item_data.get('discount', 0)))
            
            # Tax (use enterprise default or item-specific)
            tax_rate = enterprise.configuration.tax_rate
            line_after_discount = line_subtotal - discount_amount
            tax_amount = (line_after_discount * tax_rate) / 100
            
            # Line total
            line_total = line_after_discount + tax_amount
            
            # Create sale item
            SaleItem.objects.create(
                sale=sale,
                stock_item=stock_item,
                quantity=quantity,
                unit_price=unit_price,
                unit_cost=stock_item.cost_price or Decimal('0'),  # Use 0 if cost_price is None
                discount_amount=discount_amount,
                discount_percentage=0,
                tax_rate=tax_rate,
                tax_amount=tax_amount,
                subtotal=line_subtotal,
                total=line_total
            )
            
            subtotal += line_subtotal
            total_discount += discount_amount
            total_tax += tax_amount
        
        # Update sale totals
        sale.subtotal = subtotal
        sale.discount_amount = total_discount
        sale.tax_amount = total_tax
        sale.total_amount = subtotal - total_discount + total_tax
        sale.amount_paid = sale.total_amount  # Assume full payment for now
        sale.save()
        
        return sale
    
    @staticmethod
    @transaction.atomic
    def complete_sale(sale):
        """
        Complete a sale and deduct stock if configured.
        Also creates finance transactions if enabled.
        
        Args:
            sale: Sale instance
        
        Returns:
            Updated Sale instance
        
        Raises:
            ValueError: If sale is not in draft status or stock insufficient
        """
        if sale.status != 'draft':
            raise ValueError(f"Cannot complete sale with status '{sale.status}'")
        
        config = sale.enterprise.configuration
        
        # Check if sales should affect stock
        if config.stock_management_enabled and config.sales_affect_stock:
            # Verify stock availability first
            for sale_item in sale.items.all():
                if sale_item.stock_item.quantity_on_hand < sale_item.quantity:
                    raise ValueError(
                        f"Insufficient stock for {sale_item.stock_item.name}. "
                        f"Available: {sale_item.stock_item.quantity_on_hand}, "
                        f"Required: {sale_item.quantity}"
                    )
            
            # Deduct stock for each item
            for sale_item in sale.items.all():
                StockService.issue_stock(
                    stock_item=sale_item.stock_item,
                    quantity=sale_item.quantity,
                    user=sale.served_by,
                    notes=f"Sale #{sale.sale_number}",
                    reference=sale.sale_number,
                    source_type='sale',
                    source_id=sale.id
                )
        
        # Mark as completed
        sale.status = 'completed'
        sale.save(update_fields=['status'])
        
        # Create finance transactions if enabled
        if config.auto_create_finance_entries:
            from businesses.services.finance_integration_service import BusinessFinanceService
            try:
                BusinessFinanceService.record_sale_transaction(sale)
            except Exception as e:
                # Log error but don't fail the sale completion
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create finance transaction for sale #{sale.sale_number}: {e}")
        
        return sale
    
    @staticmethod
    @transaction.atomic
    def cancel_sale(sale, reason=''):
        """
        Cancel a sale.
        
        Args:
            sale: Sale instance
            reason: Reason for cancellation
        
        Returns:
            Updated Sale instance
        """
        if sale.status == 'cancelled':
            raise ValueError("Sale is already cancelled")
        
        if sale.status == 'completed':
            raise ValueError("Cannot cancel completed sale. Use returns instead.")
        
        sale.status = 'cancelled'
        if reason:
            sale.notes = f"{sale.notes}\nCancelled: {reason}".strip()
        sale.save()
        
        return sale
    
    # Query methods
    
    @staticmethod
    def get_daily_sales_summary(enterprise, date=None):
        """
        Get sales summary for a specific date.
        
        Args:
            enterprise: SaccoEnterprise instance
            date: Date to get summary for (defaults to today)
        
        Returns:
            dict with summary data
        """
        if date is None:
            date = timezone.now().date()
        
        from django.db.models import Sum, Count, Avg
        
        sales = Sale.objects.filter(
            enterprise=enterprise,
            sale_date=date,
            status='completed'
        )
        
        summary = sales.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('total_amount'),
            total_discount=Sum('discount_amount'),
            total_tax=Sum('tax_amount'),
            average_sale=Avg('total_amount')
        )
        
        # Calculate total cost and profit
        total_cost = Decimal('0')
        for sale in sales:
            total_cost += sale.total_cost
        
        total_profit = (summary['total_revenue'] or Decimal('0')) - total_cost
        
        return {
            'date': date,
            'total_sales': summary['total_sales'] or 0,
            'total_revenue': summary['total_revenue'] or Decimal('0'),
            'total_discount': summary['total_discount'] or Decimal('0'),
            'total_tax': summary['total_tax'] or Decimal('0'),
            'average_sale': summary['average_sale'] or Decimal('0'),
            'total_cost': total_cost,
            'total_profit': total_profit,
            'profit_margin': (total_profit / summary['total_revenue'] * 100) if summary['total_revenue'] else 0
        }
    
    @staticmethod
    def get_sales_by_period(enterprise, start_date, end_date):
        """
        Get sales for a date range.
        
        Args:
            enterprise: SaccoEnterprise instance
            start_date: Start date
            end_date: End date
        
        Returns:
            QuerySet of Sale instances
        """
        return Sale.objects.filter(
            enterprise=enterprise,
            sale_date__gte=start_date,
            sale_date__lte=end_date,
            status='completed'
        ).order_by('-sale_date', '-created_at')
    
    @staticmethod
    def get_top_selling_products(enterprise, limit=10, start_date=None, end_date=None):
        """
        Get top selling products by quantity.
        
        Args:
            enterprise: SaccoEnterprise instance
            limit: Number of products to return
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            List of dicts with product and quantity sold
        """
        from django.db.models import Sum
        
        sale_items = SaleItem.objects.filter(
            sale__enterprise=enterprise,
            sale__status='completed'
        )
        
        if start_date:
            sale_items = sale_items.filter(sale__sale_date__gte=start_date)
        
        if end_date:
            sale_items = sale_items.filter(sale__sale_date__lte=end_date)
        
        top_products = sale_items.values(
            'stock_item__id',
            'stock_item__name',
            'stock_item__sku'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total')
        ).order_by('-total_quantity')[:limit]
        
        return list(top_products)
