from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    # Write-only helpers to target an object
    target_type = serializers.CharField(write_only=True, required=False)
    target_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Comment
        fields = (
            'id', 'content', 'author', 'author_name',
            'parent', 'is_internal',
            'content_type', 'object_id', 'created_at', 'updated_at',
            'target_type', 'target_id'
        )
        read_only_fields = ('author', 'created_at', 'updated_at', 'content_type', 'object_id')

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
