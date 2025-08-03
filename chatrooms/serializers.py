from rest_framework import serializers
from .models import (
    Channel, ChannelMember, ChannelMessage, MessageFileUpload,
    DirectThread, DirectMessage, DirectMessageFile
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


class ChannelMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelMember
        fields = ['id', 'channel', 'user', 'is_admin', 'joined_at']


class ChannelSerializer(serializers.ModelSerializer):
    members = ChannelMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Channel
        fields = ['id', 'name', 'type', 'is_private', 'created_by', 'description', 'members']


class DirectMessageFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectMessageFile
        fields = ['id', 'file', 'uploaded_at']


class DirectMessageSerializer(serializers.ModelSerializer):
    attachments = DirectMessageFileSerializer(many=True, read_only=True)

    class Meta:
        model = DirectMessage
        fields = ['id', 'thread', 'sender', 'content', 'timestamp', 'attachments']


class DirectThreadSerializer(serializers.ModelSerializer):
    messages = DirectMessageSerializer(many=True, read_only=True)

    class Meta:
        model = DirectThread
        fields = ['id', 'user_1', 'user_2', 'created_at', 'messages']
