from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from users.models import User
from .models import Permission, PermissionGroup, PermissionLog, PermissionAction, PermissionType, PermissionScope


class ContentTypeSerializer(serializers.ModelSerializer):
    """Serializer for ContentType model"""
    
    class Meta:
        model = ContentType
        fields = ['id', 'app_label', 'model']


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""
    
    content_type_display = serializers.SerializerMethodField()
    users_display = serializers.SerializerMethodField()
    groups_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'description', 'action', 'permission_type', 'scope',
            'content_type', 'content_type_display', 'object_id', 'field_name',
            'users', 'users_display', 'groups', 'groups_display',
            'conditions', 'priority', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_content_type_display(self, obj):
        """Get human-readable content type"""
        return f"{obj.content_type.app_label}.{obj.content_type.model}"
    
    def get_users_display(self, obj):
        """Get user display names"""
        return [
            {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name()
            }
            for user in obj.users.all()
        ]
    
    def get_groups_display(self, obj):
        """Get group display names"""
        return [
            {
                'id': group.id,
                'name': group.name
            }
            for group in obj.groups.all()
        ]


class PermissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating permissions"""
    
    content_type_str = serializers.CharField(write_only=True, help_text="Content type as 'app_label.model'")
    
    class Meta:
        model = Permission
        fields = [
            'name', 'description', 'action', 'permission_type', 'scope',
            'content_type_str', 'object_id', 'field_name',
            'users', 'groups', 'conditions', 'priority', 'is_active'
        ]
    
    def validate_content_type_str(self, value):
        """Validate and convert content type string to ContentType instance"""
        try:
            app_label, model = value.split('.')
            return ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError("Invalid content type. Use format 'app_label.model'")
    
    def create(self, validated_data):
        """Create permission with content type conversion"""
        content_type = validated_data.pop('content_type_str')
        validated_data['content_type'] = content_type
        
        users = validated_data.pop('users', [])
        groups = validated_data.pop('groups', [])
        
        permission = Permission.objects.create(**validated_data)
        
        if users:
            permission.users.set(users)
        if groups:
            permission.groups.set(groups)
        
        return permission


class PermissionGroupSerializer(serializers.ModelSerializer):
    """Serializer for PermissionGroup model"""
    
    permissions_display = serializers.SerializerMethodField()
    users_display = serializers.SerializerMethodField()
    groups_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PermissionGroup
        fields = [
            'id', 'name', 'description', 'permissions', 'permissions_display',
            'users', 'users_display', 'groups', 'groups_display',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_permissions_display(self, obj):
        """Get permission display info"""
        return [
            {
                'id': perm.id,
                'name': perm.name,
                'action': perm.action,
                'permission_type': perm.permission_type,
                'content_type': f"{perm.content_type.app_label}.{perm.content_type.model}"
            }
            for perm in obj.permissions.all()
        ]
    
    def get_users_display(self, obj):
        """Get user display names"""
        return [
            {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name()
            }
            for user in obj.users.all()
        ]
    
    def get_groups_display(self, obj):
        """Get group display names"""
        return [
            {
                'id': group.id,
                'name': group.name
            }
            for group in obj.groups.all()
        ]


class PermissionLogSerializer(serializers.ModelSerializer):
    """Serializer for PermissionLog model"""
    
    user_display = serializers.SerializerMethodField()
    content_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PermissionLog
        fields = [
            'id', 'user', 'user_display', 'action', 'content_type',
            'content_type_display', 'object_id', 'field_name',
            'permission_granted', 'permissions_applied',
            'request_ip', 'user_agent', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_user_display(self, obj):
        """Get user display info"""
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'full_name': obj.user.get_full_name()
        }
    
    def get_content_type_display(self, obj):
        """Get content type display"""
        return f"{obj.content_type.app_label}.{obj.content_type.model}"


class UserPermissionSummarySerializer(serializers.Serializer):
    """Serializer for user permission summary"""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    permissions = serializers.ListField(child=serializers.DictField())
    permission_groups = serializers.ListField(child=serializers.DictField())


class PermissionCheckSerializer(serializers.Serializer):
    """Serializer for permission check requests"""
    
    action = serializers.ChoiceField(choices=PermissionAction.choices)
    content_type = serializers.CharField(help_text="Content type as 'app_label.model'")
    object_id = serializers.IntegerField(required=False, allow_null=True)
    field_name = serializers.CharField(required=False, allow_blank=True)
    
    def validate_content_type(self, value):
        """Validate content type format"""
        try:
            app_label, model = value.split('.')
            ContentType.objects.get(app_label=app_label, model=model)
            return value
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError("Invalid content type. Use format 'app_label.model'")


class PermissionCheckResponseSerializer(serializers.Serializer):
    """Serializer for permission check responses"""
    
    has_permission = serializers.BooleanField()
    action = serializers.CharField()
    content_type = serializers.CharField()
    object_id = serializers.IntegerField(allow_null=True)
    field_name = serializers.CharField(allow_blank=True)
    applied_permissions = serializers.ListField(child=serializers.DictField())


class BulkPermissionAssignSerializer(serializers.Serializer):
    """Serializer for bulk permission assignment"""
    
    permission_ids = serializers.ListField(child=serializers.IntegerField())
    user_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    group_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    action = serializers.ChoiceField(choices=['assign', 'remove'])
    
    def validate(self, data):
        """Validate that at least one target is specified"""
        if not data.get('user_ids') and not data.get('group_ids'):
            raise serializers.ValidationError("Must specify at least one user_id or group_id")
        return data


class PermissionTemplateSerializer(serializers.Serializer):
    """Serializer for permission templates"""
    
    name = serializers.CharField()
    description = serializers.CharField()
    permissions = serializers.ListField(child=serializers.DictField())
    
    def validate_permissions(self, value):
        """Validate permission template structure"""
        required_fields = ['action', 'content_type', 'permission_type']
        
        for perm in value:
            for field in required_fields:
                if field not in perm:
                    raise serializers.ValidationError(f"Permission missing required field: {field}")
        
        return value


class ContentTypePermissionSerializer(serializers.Serializer):
    """Serializer for content type permission overview"""
    
    content_type = serializers.CharField()
    model_name = serializers.CharField()
    permissions = serializers.ListField(child=serializers.DictField())
    user_count = serializers.IntegerField()
    group_count = serializers.IntegerField()
