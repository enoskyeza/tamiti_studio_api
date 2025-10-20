from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SaccoEnterpriseViewSet,
    StockItemViewSet,
    StockMovementViewSet,
    SaleViewSet
)

# Router for main resources
router = DefaultRouter()

# Phase 1: Business Management
router.register(r'enterprises', SaccoEnterpriseViewSet, basename='enterprise')

# Phase 2: Stock Management
router.register(r'stock', StockItemViewSet, basename='stock')
router.register(r'stock-movements', StockMovementViewSet, basename='stock-movement')

# Phase 3: Sales Management
router.register(r'sales', SaleViewSet, basename='sale')

urlpatterns = [
    path('', include(router.urls)),
]
