from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EventViewSet, TicketTypeViewSet, BatchViewSet, TicketViewSet,
    ScanLogViewSet, DashboardViewSet, TemporaryUserViewSet, TicketingUsersViewSet,
    TemporaryUserCreateViewSet
)
from .viewsets import EventMembershipViewSet, BatchMembershipViewSet

router = DefaultRouter()
router.register(r'events', EventViewSet)
router.register(r'ticket-types', TicketTypeViewSet)  # DEPRECATED - not used by frontend
router.register(r'batches', BatchViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'scan-logs', ScanLogViewSet)
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'temporary-users', TemporaryUserViewSet)  # DEPRECATED - use create-temporary-users instead
router.register(r'ticketing-users', TicketingUsersViewSet, basename='ticketing-users')
# New unified membership system
router.register(r'event-memberships', EventMembershipViewSet, basename='event-memberships')
router.register(r'batch-memberships', BatchMembershipViewSet, basename='batch-memberships')
# Temporary user creation endpoint
router.register(r'create-temporary-users', TemporaryUserCreateViewSet, basename='create-temporary-users')

urlpatterns = [
    path('', include(router.urls)),
    # Removed temp-login endpoint - all users now use standard JWT authentication
]
