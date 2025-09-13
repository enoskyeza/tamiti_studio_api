from rest_framework.routers import DefaultRouter
from django.urls import path
from finance import views

router = DefaultRouter()
router.register(r'parties', views.PartyViewSet)
router.register(r'accounts', views.AccountViewSet, basename='accounts')
router.register(r'invoices', views.InvoiceViewSet)
router.register(r'requisitions', views.RequisitionViewSet)
router.register(r'goals', views.GoalViewSet)
router.register(r'goal-milestones', views.GoalMilestoneViewSet)
router.register(r'transactions', views.TransactionViewSet, basename='transactions')
router.register(r'payments', views.PaymentViewSet)
router.register(r'debts', views.DebtsViewSet, basename='debts')
router.register(r'quotations', views.QuotationViewSet)
router.register(r'receipts', views.ReceiptViewSet)
router.register(r'invoice-items', views.InvoiceItemViewSet)
router.register(r'quotation-items', views.QuotationItemViewSet)
router.register(r'receipt-items', views.ReceiptItemViewSet)
router.register(r'party-finance', views.PartyFinanceViewSet, basename='party-finance')

# Personal Finance ViewSets
router.register(r'personal/accounts', views.PersonalAccountViewSet, basename='personal-accounts')
router.register(r'personal/transactions', views.PersonalTransactionViewSet, basename='personal-transactions')
router.register(r'personal/budgets', views.PersonalBudgetViewSet, basename='personal-budgets')
router.register(r'personal/savings-goals', views.PersonalSavingsGoalViewSet, basename='personal-savings-goals')
router.register(r'personal/recurring-transactions', views.PersonalTransactionRecurringViewSet, basename='personal-recurring-transactions')

# Account Transfer and Debt Management ViewSets
router.register(r'personal/transfers', views.PersonalAccountTransferViewSet, basename='personal-transfers')
router.register(r'personal/debts', views.PersonalDebtViewSet, basename='personal-debts')
router.register(r'personal/loans', views.PersonalLoanViewSet, basename='personal-loans')
router.register(r'personal/debt-payments', views.DebtPaymentViewSet, basename='personal-debt-payments')
router.register(r'personal/loan-repayments', views.LoanRepaymentViewSet, basename='personal-loan-repayments')

urlpatterns = router.urls + [
    path('summary/', views.FinanceSummaryView.as_view(), name='finance-summary'),
    path('personal/dashboard/', views.PersonalFinanceDashboardView.as_view(), name='personal-finance-dashboard'),
    path('personal/debt-summary/', views.DebtSummaryAPIView.as_view(), name='personal-debt-summary'),
]
