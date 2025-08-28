from rest_framework import viewsets, permissions, generics
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


class UserListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().select_related(
        'staff_profile__department',
        'staff_profile__designation',
        'staff_profile__branch',
        'staff_profile__role',
        'customer_profile__referred_by'
    )
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['username', 'email', 'phone']


class VirtualAssistantListView(generics.ListAPIView):
    serializer_class = VirtualAssistantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StaffProfile.objects.filter(
            role__is_virtual=True,
            is_deleted=False
        ).select_related(
            'role', 'department', 'designation', 'branch', 'assigned_to', 'created_by'
        )