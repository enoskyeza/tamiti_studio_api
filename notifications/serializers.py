from rest_framework import serializers
from users.models import User
from .models import Notification


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class NotificationSerializer(serializers.ModelSerializer):
    actor = ActorSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'actor', 'verb', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']
