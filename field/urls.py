from rest_framework.routers import DefaultRouter
from field.views import ZoneViewSet, LeadViewSet, VisitViewSet, LeadActionViewSet

router = DefaultRouter()
router.register(r'zones', ZoneViewSet)
router.register(r'leads', LeadViewSet)
router.register(r'visits', VisitViewSet)
router.register(r'actions', LeadActionViewSet)

urlpatterns = router.urls
