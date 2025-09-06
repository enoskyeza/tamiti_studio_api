from rest_framework.routers import DefaultRouter
from django.urls import path
from finance import views

router = DefaultRouter()
router.register(r'parties', views.PartyViewSet)
router.register(r'accounts', views.AccountViewSet)
router.register(r'invoices', views.InvoiceViewSet)
router.register(r'requisitions', views.RequisitionViewSet)
router.register(r'goals', views.GoalViewSet)
router.register(r'goal-milestones', views.GoalMilestoneViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'debts', views.DebtsViewSet, basename='debts')
router.register(r'quotations', views.QuotationViewSet)
router.register(r'receipts', views.ReceiptViewSet)
router.register(r'invoice-items', views.InvoiceItemViewSet)
router.register(r'quotation-items', views.QuotationItemViewSet)
router.register(r'receipt-items', views.ReceiptItemViewSet)
router.register(r'party-finance', views.PartyFinanceViewSet, basename='party-finance')

urlpatterns = router.urls + [
    path('summary/', views.FinanceSummaryView.as_view(), name='finance-summary'),
]
