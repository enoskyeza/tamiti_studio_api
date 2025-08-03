from rest_framework.routers import DefaultRouter
from accounts.views import *

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'designations', DesignationViewSet)
router.register(r'branches', BranchViewSet)
router.register(r'staff-roles', StaffRoleViewSet)
router.register(r'staff-profiles', StaffProfileViewSet)
router.register(r'customer-profiles', CustomerProfileViewSet)

urlpatterns = router.urls
