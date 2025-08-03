from rest_framework.routers import DefaultRouter
from finance import views

router = DefaultRouter()
router.register(r'parties', views.PartyViewSet)
router.register(r'accounts', views.AccountViewSet)
router.register(r'invoices', views.InvoiceViewSet)
router.register(r'requisitions', views.RequisitionViewSet)
router.register(r'goals', views.GoalViewSet)
router.register(r'transactions', views.TransactionViewSet)
router.register(r'payments', views.PaymentViewSet)

urlpatterns = router.urls
