from rest_framework import serializers
from .models import VACommand


class AssistantChatSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)


class AssistantResponseSerializer(serializers.Serializer):
    assistant = serializers.CharField()
    response = serializers.CharField()


class VACommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = VACommand
        fields = [
            'id', 'trigger_text', 'match_type', 'response_mode',
            'response_text', 'api_endpoint'
        ]
