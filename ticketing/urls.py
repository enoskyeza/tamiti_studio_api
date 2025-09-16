from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EventViewSet, TicketTypeViewSet, BatchViewSet, TicketViewSet,
    ScanLogViewSet, DashboardViewSet, TemporaryUserViewSet, TicketingUsersViewSet, temp_user_login
)

router = DefaultRouter()
router.register(r'events', EventViewSet)
router.register(r'ticket-types', TicketTypeViewSet)
router.register(r'batches', BatchViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'scan-logs', ScanLogViewSet)
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'temporary-users', TemporaryUserViewSet)
router.register(r'ticketing-users', TicketingUsersViewSet, basename='ticketing-users')

urlpatterns = [
    path('', include(router.urls)),
    path('temp-login/', temp_user_login, name='temp_user_login'),
]
