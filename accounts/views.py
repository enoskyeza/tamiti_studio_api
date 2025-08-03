from rest_framework import viewsets, permissions
from accounts.models import *
from accounts.serializers import *

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

class DepartmentViewSet(BaseViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

class DesignationViewSet(BaseViewSet):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer

class BranchViewSet(BaseViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

class StaffRoleViewSet(BaseViewSet):
    queryset = StaffRole.objects.all()
    serializer_class = StaffRoleSerializer

class StaffProfileViewSet(BaseViewSet):
    queryset = StaffProfile.objects.all()
    serializer_class = StaffProfileSerializer

class CustomerProfileViewSet(BaseViewSet):
    queryset = CustomerProfile.objects.all()
    serializer_class = CustomerProfileSerializer
