from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_email = serializers.EmailField(source='author.email', read_only=True)
    author_avatar = serializers.CharField(source='author.avatar', read_only=True)
    
    # Thread support
    is_reply = serializers.ReadOnlyField()
    reply_count = serializers.ReadOnlyField()
    replies = serializers.SerializerMethodField()
    
    # Mentions support
    mentioned_users = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    mentioned_users_details = serializers.SerializerMethodField()
    
    # Editing support
    is_edited = serializers.ReadOnlyField()
    edited_at = serializers.ReadOnlyField()

    # Write-only helpers to target an object
    target_type = serializers.CharField(write_only=True, required=False)
    target_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'author', 'author_name', 'author_email', 'author_avatar',
            'parent', 'is_internal', 'is_reply', 'reply_count', 'replies',
            'mentioned_users', 'mentioned_users_details', 'is_edited', 'edited_at',
            'content_type', 'object_id', 'created_at', 'updated_at',
            'target_type', 'target_id'
        )
        read_only_fields = ('author', 'created_at', 'updated_at', 'content_type', 'object_id')

    def get_replies(self, obj):
        """Get replies for this comment (only if it's not a reply itself)"""
        if not obj.is_reply:
            replies = obj.replies.all().order_by('created_at')
            return CommentReplySerializer(replies, many=True).data
        return []

    def get_mentioned_users_details(self, obj):
        """Get details of mentioned users"""
        return [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
                'avatar': getattr(user, 'avatar', None)
            }
            for user in obj.mentioned_users.all()
        ]

    def _resolve_target(self, attrs):
        target_type = attrs.pop('target_type', None)
        target_id = attrs.pop('target_id', None)
        if not target_type or target_id is None:
            raise serializers.ValidationError({'target': 'target_type and target_id are required'})
        try:
            app_label, model = target_type.lower().split('.')
            ct = ContentType.objects.get(app_label=app_label, model=model)
        except Exception:  # pragma: no cover - validation path
            raise serializers.ValidationError({'target_type': 'Invalid target_type. Use app_label.model'})
        return ct, target_id

    def validate_parent(self, value):
        """Ensure replies are only 1 level deep"""
        if value and value.parent:
            raise serializers.ValidationError("Cannot reply to a reply. Comments can only be nested 1 level deep.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError({'auth': 'Authentication required'})
        # Allow either direct content_type/object_id or target_type/target_id
        ct = validated_data.pop('content_type', None)
        obj_id = validated_data.pop('object_id', None)
        if not ct or obj_id is None:
            ct, obj_id = self._resolve_target(validated_data)
        return Comment.objects.create(
            author=request.user,
            content=validated_data['content'],
            parent=validated_data.get('parent'),
            is_internal=validated_data.get('is_internal', True),
            content_type=ct,
            object_id=obj_id,
        )

    def update(self, instance, validated_data):
        """Update comment and track editing"""
        from django.utils import timezone
        
        # Only allow updating content
        if 'content' in validated_data:
            instance.content = validated_data['content']
            instance.is_edited = True
            instance.edited_at = timezone.now()
            instance.save()
        return instance


class CommentReplySerializer(serializers.ModelSerializer):
    """Simplified serializer for replies to avoid infinite recursion"""
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_email = serializers.EmailField(source='author.email', read_only=True)
    author_avatar = serializers.CharField(source='author.avatar', read_only=True)
    mentioned_users_details = serializers.SerializerMethodField()
    is_edited = serializers.ReadOnlyField()
    edited_at = serializers.ReadOnlyField()

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'author', 'author_name', 'author_email', 'author_avatar',
            'parent', 'is_internal', 'mentioned_users_details', 'is_edited', 'edited_at',
            'created_at', 'updated_at'
        )
        read_only_fields = ('author', 'created_at', 'updated_at', 'parent')

    def get_mentioned_users_details(self, obj):
        """Get details of mentioned users"""
        return [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
                'avatar': getattr(user, 'avatar', None)
            }
            for user in obj.mentioned_users.all()
        ]


class MentionSearchSerializer(serializers.Serializer):
    """Serializer for mention search functionality"""
    query = serializers.CharField(max_length=100)
    
    
class UserMentionSerializer(serializers.Serializer):
    """Serializer for user mention suggestions"""
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    avatar = serializers.CharField(allow_null=True)
