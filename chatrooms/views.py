from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import (
    Channel, ChannelMessage, ChannelMember,
    DirectThread, DirectMessage
)
from .serializers import (
    ChannelSerializer, ChannelMessageSerializer,
    ChannelMemberSerializer, DirectThreadSerializer, DirectMessageSerializer
)


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ChannelMessageViewSet(viewsets.ModelViewSet):
    queryset = ChannelMessage.objects.all()
    serializer_class = ChannelMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(channel__members__user=self.request.user)


class ChannelMemberViewSet(viewsets.ModelViewSet):
    queryset = ChannelMember.objects.all()
    serializer_class = ChannelMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class DirectThreadViewSet(viewsets.ModelViewSet):
    queryset = DirectThread.objects.all()
    serializer_class = DirectThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user_1=self.request.user) | self.queryset.filter(user_2=self.request.user)


class DirectMessageViewSet(viewsets.ModelViewSet):
    queryset = DirectMessage.objects.all()
    serializer_class = DirectMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(thread__user_1=self.request.user) | self.queryset.filter(thread__user_2=self.request.user)
