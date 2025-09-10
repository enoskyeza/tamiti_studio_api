from rest_framework import serializers
from accounts.models import Department, Designation, Branch, StaffRole, StaffProfile, CustomerProfile
from users.models import User


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'


class DesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = '__all__'


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = '__all__'


class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = '__all__'


class StaffProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffProfile
        fields = '__all__'


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = '__all__'


class UserListSerializer(serializers.ModelSerializer):
    staff_profile = StaffProfileSerializer(read_only=True)
    customer_profile = CustomerProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'role', 'is_active',
            'staff_profile', 'customer_profile'
        ]


class StaffRoleViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = ['id', 'dashboard_url', 'title']


class VirtualAssistantSerializer(serializers.ModelSerializer):
    department = serializers.StringRelatedField()
    designation = serializers.StringRelatedField()
    branch = serializers.StringRelatedField()
    role = StaffRoleViewSerializer(read_only=True)

    class Meta:
        model = StaffProfile
        fields = ['id', 'name', 'role', 'department', "designation", "branch"]
