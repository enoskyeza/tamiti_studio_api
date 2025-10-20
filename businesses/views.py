from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    SaccoEnterprise, EnterpriseConfiguration,
    StockItem, StockMovement,
    Sale, SaleItem
)
from .serializers import (
    SaccoEnterpriseSerializer,
    SaccoEnterpriseCreateSerializer,
    EnterpriseConfigurationSerializer,
    StockItemSerializer,
    StockMovementSerializer,
    SaleSerializer,
    SaleCreateSerializer
)
from .services.business_service import BusinessService
from .services.stock_service import StockService
from .services.sales_service import SalesService
from .services.finance_integration_service import BusinessFinanceService


class SaccoEnterpriseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SACCO Enterprise management.
    Phase 1: Business Module
    """
    queryset = SaccoEnterprise.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SaccoEnterpriseCreateSerializer
        return SaccoEnterpriseSerializer
    
    def get_queryset(self):
        """Filter businesses by SACCO membership"""
        queryset = SaccoEnterprise.objects.select_related(
            'sacco', 'finance_account', 'configuration'
        ).prefetch_related('managed_by')
        
        # Filter by SACCO if specified
        sacco_id = self.request.query_params.get('sacco')
        if sacco_id:
            queryset = queryset.filter(sacco_id=sacco_id)
        
        # Staff can see all
        if self.request.user.is_staff or self.request.user.is_superuser:
            return queryset
        
        # Regular users see only their SACCO's businesses
        if hasattr(self.request.user, 'sacco_membership'):
            return queryset.filter(
                sacco=self.request.user.sacco_membership.sacco
            )
        
        return SaccoEnterprise.objects.none()
    
    @action(detail=True, methods=['post'])
    def configure(self, request, pk=None):
        """
        Update enterprise configuration.
        
        POST /api/businesses/enterprises/{id}/configure/
        {
            "stock_management_enabled": true,
            "sales_management_enabled": true,
            "auto_create_finance_entries": true,
            "sales_affect_stock": true
        }
        """
        enterprise = self.get_object()
        
        serializer = EnterpriseConfigurationSerializer(
            enterprise.configuration,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def accounts(self, request, pk=None):
        """
        Get all finance accounts for this business.
        
        GET /api/businesses/enterprises/{id}/accounts/
        """
        enterprise = self.get_object()
        accounts = BusinessService.get_business_accounts(enterprise)
        
        account_data = {}
        for key, account in accounts.items():
            account_data[key] = {
                'id': account.id,
                'name': account.name,
                'account_type': account.account_type,
                'balance': account.balance
            }
        
        return Response(account_data)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """
        Archive (soft delete) a business.
        
        POST /api/businesses/enterprises/{id}/archive/
        """
        enterprise = self.get_object()
        BusinessService.archive_business(enterprise)
        
        return Response({
            'message': f'Business "{enterprise.name}" has been archived',
            'is_active': enterprise.is_active
        })
    
    @action(detail=True, methods=['get'])
    def profit_loss(self, request, pk=None):
        """
        Get Profit & Loss statement for the business.
        
        GET /api/businesses/enterprises/{id}/profit_loss/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        """
        enterprise = self.get_object()
        
        # Get date parameters
        from datetime import datetime, timedelta
        end_date_str = request.query_params.get('end_date')
        start_date_str = request.query_params.get('start_date')
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = end_date - timedelta(days=30)
        
        pl_data = BusinessFinanceService.get_profit_and_loss(
            enterprise, start_date, end_date
        )
        
        return Response(pl_data)
    
    @action(detail=True, methods=['get'])
    def cash_flow(self, request, pk=None):
        """
        Get Cash Flow statement for the business.
        
        GET /api/businesses/enterprises/{id}/cash_flow/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        """
        enterprise = self.get_object()
        
        # Get date parameters
        from datetime import datetime, timedelta
        end_date_str = request.query_params.get('end_date')
        start_date_str = request.query_params.get('start_date')
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
        
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = end_date - timedelta(days=30)
        
        cf_data = BusinessFinanceService.get_cash_flow(
            enterprise, start_date, end_date
        )
        
        return Response(cf_data)


# ============================================================================
# PHASE 2: STOCK MANAGEMENT VIEWS
# ============================================================================


class StockItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Stock Item management.
    Phase 2: Stock Management
    """
    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter stock by enterprise"""
        queryset = StockItem.objects.select_related('enterprise').all()
        
        # Filter by enterprise
        enterprise_id = self.request.query_params.get('enterprise')
        if enterprise_id:
            queryset = queryset.filter(enterprise_id=enterprise_id)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter low stock
        low_stock = self.request.query_params.get('low_stock')
        if low_stock and low_stock.lower() == 'true':
            queryset = queryset.filter(quantity_on_hand__lte=models.F('reorder_level'))
        
        return queryset.order_by('name')
    
    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """
        Receive stock (stock in).
        
        POST /api/businesses/stock/{id}/receive/
        {
            "quantity": 100,
            "unit_cost": 5000,
            "notes": "Purchase from supplier",
            "reference": "PO-001"
        }
        """
        item = self.get_object()
        
        try:
            quantity = int(request.data.get('quantity'))
            unit_cost = request.data.get('unit_cost')
            notes = request.data.get('notes', '')
            reference = request.data.get('reference', '')
            
            movement = StockService.receive_stock(
                stock_item=item,
                quantity=quantity,
                unit_cost=unit_cost,
                user=request.user,
                notes=notes,
                reference=reference
            )
            
            return Response({
                'message': f'Received {quantity} units of {item.name}',
                'movement_id': movement.id,
                'new_quantity': item.quantity_on_hand,
                'movement': StockMovementSerializer(movement).data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """
        Issue stock (stock out).
        
        POST /api/businesses/stock/{id}/issue/
        {
            "quantity": 10,
            "notes": "Issued for sale",
            "reference": "SALE-001"
        }
        """
        item = self.get_object()
        
        try:
            quantity = int(request.data.get('quantity'))
            notes = request.data.get('notes', '')
            reference = request.data.get('reference', '')
            
            movement = StockService.issue_stock(
                stock_item=item,
                quantity=quantity,
                user=request.user,
                notes=notes,
                reference=reference
            )
            
            return Response({
                'message': f'Issued {quantity} units of {item.name}',
                'movement_id': movement.id,
                'new_quantity': item.quantity_on_hand,
                'movement': StockMovementSerializer(movement).data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """
        Adjust stock to specific quantity.
        
        POST /api/businesses/stock/{id}/adjust/
        {
            "new_quantity": 95,
            "reason": "Physical count correction"
        }
        """
        item = self.get_object()
        
        try:
            new_quantity = int(request.data.get('new_quantity'))
            reason = request.data.get('reason', '')
            
            movement = StockService.adjust_stock(
                stock_item=item,
                new_quantity=new_quantity,
                reason=reason,
                user=request.user
            )
            
            return Response({
                'message': f'Adjusted {item.name} to {new_quantity} units',
                'movement_id': movement.id,
                'old_quantity': new_quantity - movement.quantity,
                'new_quantity': new_quantity,
                'difference': movement.quantity,
                'movement': StockMovementSerializer(movement).data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def damage(self, request, pk=None):
        """
        Record damaged/lost stock.
        
        POST /api/businesses/stock/{id}/damage/
        {
            "quantity": 5,
            "reason": "Broken during transport"
        }
        """
        item = self.get_object()
        
        try:
            quantity = int(request.data.get('quantity'))
            reason = request.data.get('reason', '')
            
            movement = StockService.record_damage(
                stock_item=item,
                quantity=quantity,
                reason=reason,
                user=request.user
            )
            
            return Response({
                'message': f'Recorded {quantity} units of {item.name} as damaged/lost',
                'movement_id': movement.id,
                'new_quantity': item.quantity_on_hand,
                'movement': StockMovementSerializer(movement).data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        Get items with low stock.
        
        GET /api/businesses/stock/low_stock/?enterprise={id}
        """
        enterprise_id = request.query_params.get('enterprise')
        if not enterprise_id:
            return Response(
                {'error': 'enterprise parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        items = StockService.get_low_stock_items(enterprise)
        
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get stock summary for enterprise.
        
        GET /api/businesses/stock/summary/?enterprise={id}
        """
        enterprise_id = request.query_params.get('enterprise')
        if not enterprise_id:
            return Response(
                {'error': 'enterprise parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        summary = StockService.get_stock_summary(enterprise)
        
        return Response(summary)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Stock Movement history (read-only).
    Phase 2: Stock Management
    """
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter movements"""
        queryset = StockMovement.objects.select_related(
            'stock_item', 'stock_item__enterprise', 'recorded_by'
        ).all()
        
        # Filter by enterprise
        enterprise_id = self.request.query_params.get('enterprise')
        if enterprise_id:
            queryset = queryset.filter(stock_item__enterprise_id=enterprise_id)
        
        # Filter by stock item
        stock_item_id = self.request.query_params.get('stock_item')
        if stock_item_id:
            queryset = queryset.filter(stock_item_id=stock_item_id)
        
        # Filter by movement type
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(movement_date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(movement_date__lte=end_date)
        
        return queryset.order_by('-movement_date', '-created_at')


# Import models for F expression
from django.db import models


# ============================================================================
# PHASE 3: SALES MANAGEMENT VIEWS
# ============================================================================


class SaleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Sale management.
    Phase 3: Sales Management
    """
    queryset = Sale.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SaleCreateSerializer
        return SaleSerializer
    
    def get_queryset(self):
        """Filter sales by enterprise"""
        queryset = Sale.objects.select_related(
            'enterprise', 'served_by'
        ).prefetch_related('items__stock_item').all()
        
        # Filter by enterprise
        enterprise_id = self.request.query_params.get('enterprise')
        if enterprise_id:
            queryset = queryset.filter(enterprise_id=enterprise_id)
        
        # Filter by status
        sale_status = self.request.query_params.get('status')
        if sale_status:
            queryset = queryset.filter(status=sale_status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(sale_date__gte=start_date)
        
        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(sale_date__lte=end_date)
        
        return queryset.order_by('-sale_date', '-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create a new sale"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        
        # Auto-complete the sale to deduct stock immediately if configured
        try:
            sale = SalesService.complete_sale(sale)
        except ValueError as e:
            # If completion fails (e.g., insufficient stock), delete the draft sale and return error
            sale.delete()
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return with full sale details
        output_serializer = SaleSerializer(sale)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete a sale (finalizes it and deducts stock if configured).
        
        POST /api/businesses/sales/{id}/complete/
        """
        sale = self.get_object()
        
        try:
            updated_sale = SalesService.complete_sale(sale)
            serializer = self.get_serializer(updated_sale)
            
            return Response({
                'message': f'Sale #{sale.sale_number} completed successfully',
                'sale': serializer.data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a sale.
        
        POST /api/businesses/sales/{id}/cancel/
        {
            "reason": "Customer cancelled order"
        }
        """
        sale = self.get_object()
        reason = request.data.get('reason', '')
        
        try:
            updated_sale = SalesService.cancel_sale(sale, reason)
            serializer = self.get_serializer(updated_sale)
            
            return Response({
                'message': f'Sale #{sale.sale_number} cancelled',
                'sale': serializer.data
            })
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def daily_summary(self, request):
        """
        Get daily sales summary.
        
        GET /api/businesses/sales/daily_summary/?enterprise={id}&date=2024-10-18
        """
        enterprise_id = request.query_params.get('enterprise')
        if not enterprise_id:
            return Response(
                {'error': 'enterprise parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        
        date_str = request.query_params.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = None
        
        summary = SalesService.get_daily_sales_summary(enterprise, date)
        
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """
        Get top selling products.
        
        GET /api/businesses/sales/top_products/?enterprise={id}&limit=10
        """
        enterprise_id = request.query_params.get('enterprise')
        if not enterprise_id:
            return Response(
                {'error': 'enterprise parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        limit = int(request.query_params.get('limit', 10))
        
        top_products = SalesService.get_top_selling_products(enterprise, limit)
        
        return Response(top_products)
    
    @action(detail=False, methods=['post'])
    def record_expense(self, request):
        """
        Record a business expense.
        
        POST /api/businesses/sales/record_expense/
        {
            "enterprise": 1,
            "amount": 50000,
            "description": "Monthly rent",
            "category": "operations",
            "date": "2024-10-20"
        }
        """
        enterprise_id = request.data.get('enterprise')
        amount = request.data.get('amount')
        description = request.data.get('description')
        category = request.data.get('category', 'operations')
        date = request.data.get('date')
        
        if not all([enterprise_id, amount, description]):
            return Response(
                {'error': 'enterprise, amount, and description are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        
        try:
            from datetime import datetime
            from decimal import Decimal
            
            expense_date = datetime.strptime(date, '%Y-%m-%d').date() if date else None
            amount_decimal = Decimal(str(amount))
            
            transaction = BusinessFinanceService.record_business_expense(
                enterprise=enterprise,
                amount=amount_decimal,
                description=description,
                category=category,
                date=expense_date
            )
            
            return Response({
                'message': 'Expense recorded successfully',
                'transaction_id': transaction.id,
                'amount': str(transaction.amount),
                'description': transaction.description
            }, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to record expense: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_expenses(self, request):
        """
        Get expenses for an enterprise.
        
        GET /api/businesses/sales/get_expenses/?enterprise={id}
        """
        enterprise_id = request.query_params.get('enterprise')
        if not enterprise_id:
            return Response(
                {'error': 'enterprise parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        enterprise = get_object_or_404(SaccoEnterprise, id=enterprise_id)
        accounts = BusinessService.get_business_accounts(enterprise)
        
        if not accounts or 'expenses' not in accounts:
            return Response([])
        
        # Get transactions from the expense account
        from finance.models import Transaction
        expenses = Transaction.objects.filter(
            account=accounts['expenses'],
            type='expense'
        ).order_by('-date', '-created_at')
        
        expense_data = [{
            'id': exp.id,
            'date': exp.date.isoformat(),
            'category': exp.category or 'operations',
            'description': exp.description,
            'amount': str(exp.amount),
            'payment_method': 'cash',  # Could be enhanced later
        } for exp in expenses]
        
        return Response(expense_data)
