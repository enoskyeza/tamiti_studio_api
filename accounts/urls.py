from django.urls import path

from rest_framework.routers import DefaultRouter

from accounts.views import (
    DepartmentViewSet,
    DesignationViewSet,
    BranchViewSet,
    StaffRoleViewSet,
    StaffProfileViewSet,
    CustomerProfileViewSet,
    UserListViewSet,
    VirtualAssistantListView,
)


router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'designations', DesignationViewSet)
router.register(r'branches', BranchViewSet)
router.register(r'staff-roles', StaffRoleViewSet)
router.register(r'staff-profiles', StaffProfileViewSet)
router.register(r'customer-profiles', CustomerProfileViewSet)
router.register(r'users-list', UserListViewSet, basename='users-list')


urlpatterns = router.urls

urlpatterns += [
    path('virtual-assistants/', VirtualAssistantListView.as_view(), name='virtual-assistants'),
]