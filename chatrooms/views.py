from django.db.models import Q
from datetime import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from .models import (
    Channel, ChannelMessage, ChannelMember, MessageFileUpload,
    DirectThread, DirectMessage, DirectMessageFile, DirectThreadReadState
)
from .serializers import (
    ChannelSerializer, ChannelMessageSerializer,
    ChannelMemberSerializer, DirectThreadSerializer, DirectMessageSerializer,
)
from .permissions import (
    IsChannelAdminOrReadOnly, CanModifyChannelMessage,
    IsThreadParticipant, CanModifyDirectMessage,
)

User = get_user_model()


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [permissions.IsAuthenticated, IsChannelAdminOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        # public channels or channels where user is a member
        return (
            Channel.objects
            .filter(Q(is_private=False) | Q(members__user=user))
            .select_related('created_by')
            .prefetch_related('members__user')
            .distinct()
        )

    def perform_create(self, serializer):
        channel = serializer.save(created_by=self.request.user)
        # auto-join creator as admin
        ChannelMember.objects.get_or_create(channel=channel, user=self.request.user, defaults={'is_admin': True})

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        channel = self.get_object()
        # Only members can view the list for private channels
        if channel.is_private and not ChannelMember.objects.filter(channel=channel, user=request.user).exists():
            return Response({'detail': 'Not a member of this private channel.'}, status=status.HTTP_403_FORBIDDEN)
        qs = ChannelMember.objects.filter(channel=channel).select_related('user')
        return Response(ChannelMemberSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        channel = self.get_object()
        # Only admins can add
        if not ChannelMember.objects.filter(channel=channel, user=request.user, is_admin=True).exists() and channel.created_by_id != request.user.id:
            return Response({'detail': 'Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            member_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        ChannelMember.objects.get_or_create(channel=channel, user=member_user)
        return Response({'detail': 'Member added.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        channel = self.get_object()
        if not ChannelMember.objects.filter(channel=channel, user=request.user, is_admin=True).exists() and channel.created_by_id != request.user.id:
            return Response({'detail': 'Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        qs = ChannelMember.objects.filter(channel=channel, user_id=user_id)
        if not qs.exists():
            return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Prevent removing the last admin
        if qs.filter(is_admin=True).exists():
            admin_count = ChannelMember.objects.filter(channel=channel, is_admin=True).count()
            if admin_count <= 1:
                return Response({'detail': 'Cannot remove the last admin.'}, status=status.HTTP_400_BAD_REQUEST)
        qs.delete()
        return Response({'detail': 'Member removed.'})

    @action(detail=True, methods=['post'])
    def promote_member(self, request, pk=None):
        channel = self.get_object()
        if not ChannelMember.objects.filter(channel=channel, user=request.user, is_admin=True).exists() and channel.created_by_id != request.user.id:
            return Response({'detail': 'Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = ChannelMember.objects.get(channel=channel, user_id=user_id)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)
        membership.is_admin = True
        membership.save(update_fields=['is_admin'])
        return Response({'detail': 'Member promoted to admin.'})

    @action(detail=True, methods=['post'])
    def demote_member(self, request, pk=None):
        channel = self.get_object()
        if not ChannelMember.objects.filter(channel=channel, user=request.user, is_admin=True).exists() and channel.created_by_id != request.user.id:
            return Response({'detail': 'Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = ChannelMember.objects.get(channel=channel, user_id=user_id)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Prevent demoting the last admin
        if membership.is_admin:
            admin_count = ChannelMember.objects.filter(channel=channel, is_admin=True).count()
            if admin_count <= 1:
                return Response({'detail': 'Cannot demote the last admin.'}, status=status.HTTP_400_BAD_REQUEST)
        membership.is_admin = False
        membership.save(update_fields=['is_admin'])
        return Response({'detail': 'Member demoted from admin.'})

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        channel = self.get_object()
        if channel.is_private:
            return Response({'detail': 'Cannot join a private channel.'}, status=status.HTTP_403_FORBIDDEN)
        ChannelMember.objects.get_or_create(channel=channel, user=request.user)
        return Response({'detail': 'Joined channel.'})

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        channel = self.get_object()
        try:
            membership = ChannelMember.objects.get(channel=channel, user=request.user)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Not a member.'}, status=status.HTTP_400_BAD_REQUEST)
        if membership.is_admin:
            admin_count = ChannelMember.objects.filter(channel=channel, is_admin=True).count()
            if admin_count <= 1:
                return Response({'detail': 'Cannot leave as the last admin.'}, status=status.HTTP_400_BAD_REQUEST)
        membership.delete()
        return Response({'detail': 'Left channel.'})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        channel = self.get_object()
        try:
            membership = ChannelMember.objects.get(channel=channel, user=request.user)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Not a member.'}, status=status.HTTP_403_FORBIDDEN)
        membership.last_read_at = timezone.now()
        membership.save(update_fields=['last_read_at'])
        return Response({'detail': 'Marked as read.', 'last_read_at': membership.last_read_at})

    @action(detail=True, methods=['post'], url_path='mark-read-up-to')
    def mark_read_up_to(self, request, pk=None):
        channel = self.get_object()
        message_id = request.data.get('message_id')
        if not message_id:
            return Response({'detail': 'message_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            message = ChannelMessage.objects.get(id=int(message_id), channel=channel)
        except (ChannelMessage.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid message.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = ChannelMember.objects.get(channel=channel, user=request.user)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Not a member.'}, status=status.HTTP_403_FORBIDDEN)
        if membership.last_read_at is None or message.timestamp > membership.last_read_at:
            membership.last_read_at = message.timestamp
            membership.save(update_fields=['last_read_at'])
        return Response({'detail': 'Marked as read up to message.', 'last_read_at': membership.last_read_at})

    @action(detail=True, methods=['get'])
    def unread_count(self, request, pk=None):
        channel = self.get_object()
        try:
            membership = ChannelMember.objects.get(channel=channel, user=request.user)
        except ChannelMember.DoesNotExist:
            return Response({'detail': 'Not a member.'}, status=status.HTTP_403_FORBIDDEN)
        last_read = membership.last_read_at or timezone.make_aware(datetime.min)
        count = ChannelMessage.objects.filter(channel=channel, timestamp__gt=last_read).exclude(sender=request.user).count()
        return Response({'unread_count': count})

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        channel = self.get_object()
        if not ChannelMember.objects.filter(channel=channel, user=request.user).exists():
            return Response({'detail': 'Not a member.'}, status=status.HTTP_403_FORBIDDEN)
        qs = (ChannelMessage.objects
              .filter(channel=channel)
              .select_related('channel', 'sender')
              .prefetch_related('attachments')
              .order_by('timestamp', 'id'))
        return Response(ChannelMessageSerializer(qs, many=True).data)


class ChannelMessageViewSet(viewsets.ModelViewSet):
    queryset = ChannelMessage.objects.all()
    serializer_class = ChannelMessageSerializer
    permission_classes = [permissions.IsAuthenticated, CanModifyChannelMessage]

    def get_queryset(self):
        qs = (ChannelMessage.objects
              .filter(channel__members__user=self.request.user)
              .select_related('channel', 'sender')
              .prefetch_related('attachments'))
        channel_id = self.request.query_params.get('channel')
        if channel_id:
            try:
                qs = qs.filter(channel_id=int(channel_id))
            except (ValueError, TypeError):
                pass
        return qs.order_by('timestamp', 'id')

    def perform_create(self, serializer):
        channel = serializer.validated_data.get('channel')
        if not ChannelMember.objects.filter(channel=channel, user=self.request.user).exists():
            raise permissions.PermissionDenied('You are not a member of this channel.')
        serializer.save(sender=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_attachment(self, request, pk=None):
        message = self.get_object()
        if not ChannelMember.objects.filter(channel=message.channel, user=request.user).exists():
            return Response({'detail': 'Not a member of the channel.'}, status=status.HTTP_403_FORBIDDEN)
        file = request.data.get('file')
        if not file:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        MessageFileUpload.objects.create(message=message, file=file)
        return Response(ChannelMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='create-with-file')
    def create_with_file(self, request):
        channel_id = request.data.get('channel')
        content = request.data.get('content', '')
        file = request.data.get('file')
        if not channel_id or not file:
            return Response({'detail': 'channel and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            channel = Channel.objects.get(id=int(channel_id))
        except (Channel.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid channel.'}, status=status.HTTP_400_BAD_REQUEST)
        if not ChannelMember.objects.filter(channel=channel, user=request.user).exists():
            return Response({'detail': 'Not a member of the channel.'}, status=status.HTTP_403_FORBIDDEN)
        message = ChannelMessage.objects.create(channel=channel, sender=request.user, content=content or '')
        MessageFileUpload.objects.create(message=message, file=file)
        return Response(ChannelMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class ChannelMemberViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ChannelMember.objects.all()
    serializer_class = ChannelMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (ChannelMember.objects
                .filter(user=self.request.user)
                .select_related('channel', 'user'))


class DirectThreadViewSet(viewsets.ModelViewSet):
    queryset = DirectThread.objects.all()
    serializer_class = DirectThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (DirectThread.objects
                .filter(Q(user_1=self.request.user) | Q(user_2=self.request.user))
                .select_related('user_1', 'user_2')
                .prefetch_related('messages__attachments')
                .distinct())

    def perform_create(self, serializer):
        user_2 = serializer.validated_data.get('user_2')
        if user_2 is None:
            raise permissions.PermissionDenied('user_2 is required.')
        if user_2.id == self.request.user.id:
            raise permissions.PermissionDenied('Cannot create a direct thread with yourself.')
        # Normalize order in serializer.save via model.save
        thread = serializer.save(user_1=self.request.user)
        # Initialize read states for both users
        DirectThreadReadState.objects.get_or_create(thread=thread, user=self.request.user)
        DirectThreadReadState.objects.get_or_create(thread=thread, user=user_2)

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        thread = self.get_object()
        if request.user.id not in [thread.user_1_id, thread.user_2_id]:
            return Response({'detail': 'Not a participant.'}, status=status.HTTP_403_FORBIDDEN)
        qs = (DirectMessage.objects
              .filter(thread=thread)
              .select_related('thread', 'sender')
              .prefetch_related('attachments')
              .order_by('timestamp', 'id'))
        return Response(DirectMessageSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        thread = self.get_object()
        state, _ = DirectThreadReadState.objects.get_or_create(thread=thread, user=request.user)
        state.last_read_at = timezone.now()
        state.save(update_fields=['last_read_at'])
        return Response({'detail': 'Marked as read.', 'last_read_at': state.last_read_at})

    @action(detail=True, methods=['post'], url_path='mark-read-up-to')
    def mark_read_up_to(self, request, pk=None):
        thread = self.get_object()
        message_id = request.data.get('message_id')
        if not message_id:
            return Response({'detail': 'message_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            message = DirectMessage.objects.get(id=int(message_id), thread=thread)
        except (DirectMessage.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid message.'}, status=status.HTTP_400_BAD_REQUEST)
        state, _ = DirectThreadReadState.objects.get_or_create(thread=thread, user=request.user)
        if state.last_read_at is None or message.timestamp > state.last_read_at:
            state.last_read_at = message.timestamp
            state.save(update_fields=['last_read_at'])
        return Response({'detail': 'Marked as read up to message.', 'last_read_at': state.last_read_at})

    @action(detail=True, methods=['get'])
    def unread_count(self, request, pk=None):
        thread = self.get_object()
        state, _ = DirectThreadReadState.objects.get_or_create(thread=thread, user=request.user)
        last_read = state.last_read_at or timezone.make_aware(datetime.min)
        count = DirectMessage.objects.filter(thread=thread, timestamp__gt=last_read).exclude(sender=request.user).count()
        return Response({'unread_count': count})


class DirectMessageViewSet(viewsets.ModelViewSet):
    queryset = DirectMessage.objects.all()
    serializer_class = DirectMessageSerializer
    permission_classes = [permissions.IsAuthenticated, CanModifyDirectMessage]

    def get_queryset(self):
        qs = (DirectMessage.objects
              .filter(Q(thread__user_1=self.request.user) | Q(thread__user_2=self.request.user))
              .select_related('thread', 'sender')
              .prefetch_related('attachments')
              .distinct())
        return qs.order_by('timestamp', 'id')

    def perform_create(self, serializer):
        thread = serializer.validated_data.get('thread')
        if thread.user_1_id != self.request.user.id and thread.user_2_id != self.request.user.id:
            raise permissions.PermissionDenied('Not a participant of the thread.')
        serializer.save(sender=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_attachment(self, request, pk=None):
        message = self.get_object()
        if request.user.id not in [message.thread.user_1_id, message.thread.user_2_id]:
            return Response({'detail': 'Not a participant.'}, status=status.HTTP_403_FORBIDDEN)
        file = request.data.get('file')
        if not file:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        DirectMessageFile.objects.create(message=message, file=file)
        return Response(DirectMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='create-with-file')
    def create_with_file(self, request):
        thread_id = request.data.get('thread')
        content = request.data.get('content', '')
        file = request.data.get('file')
        if not thread_id or not file:
            return Response({'detail': 'thread and file are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            thread = DirectThread.objects.get(id=int(thread_id))
        except (DirectThread.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Invalid thread.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.id not in [thread.user_1_id, thread.user_2_id]:
            return Response({'detail': 'Not a participant.'}, status=status.HTTP_403_FORBIDDEN)
        message = DirectMessage.objects.create(thread=thread, sender=request.user, content=content or '')
        DirectMessageFile.objects.create(message=message, file=file)
        return Response(DirectMessageSerializer(message).data, status=status.HTTP_201_CREATED)
