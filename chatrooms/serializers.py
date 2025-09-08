from rest_framework import serializers
from .models import (
    Channel, ChannelMember, ChannelMessage, MessageFileUpload,
    DirectThread, DirectMessage, DirectMessageFile, DirectThreadReadState
)


class MessageFileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageFileUpload
        fields = ['id', 'file', 'uploaded_at']


class ChannelMessageSerializer(serializers.ModelSerializer):
    attachments = MessageFileUploadSerializer(many=True, read_only=True)

    class Meta:
        model = ChannelMessage
        fields = ['id', 'channel', 'sender', 'content', 'timestamp', 'attachments']
        read_only_fields = ['sender', 'timestamp']

    def validate(self, attrs):
        # For standard create/update without file, ensure content is not empty
        if self.instance is None and not attrs.get('content'):
            raise serializers.ValidationError({'content': 'Message content cannot be empty.'})
        return attrs

    def update(self, instance, validated_data):
        # Prevent cross-channel moves and sender changes
        validated_data.pop('channel', None)
        validated_data.pop('sender', None)
        return super().update(instance, validated_data)


class ChannelMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelMember
        fields = ['id', 'channel', 'user', 'is_admin', 'joined_at', 'last_read_at']
        read_only_fields = ['channel', 'user', 'joined_at', 'last_read_at']


class ChannelSerializer(serializers.ModelSerializer):
    members = ChannelMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Channel
        fields = ['id', 'name', 'type', 'is_private', 'created_by', 'description', 'members', 'created_at']
        read_only_fields = ['created_by', 'created_at']


class DirectMessageFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectMessageFile
        fields = ['id', 'file', 'uploaded_at']


class DirectMessageSerializer(serializers.ModelSerializer):
    attachments = DirectMessageFileSerializer(many=True, read_only=True)

    class Meta:
        model = DirectMessage
        fields = ['id', 'thread', 'sender', 'content', 'timestamp', 'attachments']
        read_only_fields = ['sender', 'timestamp']

    def validate(self, attrs):
        if self.instance is None and not attrs.get('content'):
            raise serializers.ValidationError({'content': 'Message content cannot be empty.'})
        return attrs

    def update(self, instance, validated_data):
        # Prevent cross-thread moves and sender changes
        validated_data.pop('thread', None)
        validated_data.pop('sender', None)
        return super().update(instance, validated_data)


class DirectThreadSerializer(serializers.ModelSerializer):
    messages = DirectMessageSerializer(many=True, read_only=True)

    class Meta:
        model = DirectThread
        fields = ['id', 'user_1', 'user_2', 'created_at', 'messages']
        read_only_fields = ['user_1', 'created_at']


class DirectThreadReadStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectThreadReadState
        fields = ['id', 'thread', 'user', 'last_read_at']
        read_only_fields = ['user']
