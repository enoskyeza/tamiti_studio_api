from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import ChannelMember


class IsChannelAdminOrReadOnly(BasePermission):
    """Allow read, but writes only to channel admins or creator."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if getattr(obj, 'created_by_id', None) == getattr(request.user, 'id', None):
            return True
        return ChannelMember.objects.filter(channel=obj, user=request.user, is_admin=True).exists()


class CanModifyChannelMessage(BasePermission):
    """Only the sender can update their message; admins or sender can delete."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        is_sender = getattr(obj, 'sender_id', None) == getattr(request.user, 'id', None)
        if request.method in ['PUT', 'PATCH']:
            return is_sender
        if request.method == 'DELETE':
            if is_sender:
                return True
            # allow channel admins to delete any message in the channel
            return ChannelMember.objects.filter(channel=obj.channel, user=request.user, is_admin=True).exists()
        return False


class IsThreadParticipant(BasePermission):
    """Access limited to participants of the direct thread."""

    def has_object_permission(self, request, view, obj):
        user_id = getattr(request.user, 'id', None)
        return getattr(obj, 'user_1_id', None) == user_id or getattr(obj, 'user_2_id', None) == user_id


class CanModifyDirectMessage(BasePermission):
    """Only the sender can modify/delete a direct message."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, 'sender_id', None) == getattr(request.user, 'id', None)

