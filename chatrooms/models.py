from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import BaseModel
from common.enums import ChannelType

User = get_user_model()


class Channel(BaseModel):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ChannelType.choices)
    is_private = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_channels')
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ChannelMember(BaseModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='channel_memberships')
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} in {self.channel}"


class ChannelMessage(BaseModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} in {self.channel}: {self.content[:20]}"


class MessageFileUpload(BaseModel):
    message = models.ForeignKey(ChannelMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat/uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for message {self.message_id}"


class DirectThread(BaseModel):
    user_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='direct_threads_as_user1')
    user_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='direct_threads_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_1', 'user_2')

    def __str__(self):
        return f"Direct thread between {self.user_1} and {self.user_2}"


class DirectMessage(BaseModel):
    thread = models.ForeignKey(DirectThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender}: {self.content[:20]}"


class DirectMessageFile(BaseModel):
    message = models.ForeignKey(DirectMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat/direct_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Direct attachment for message {self.message_id}"

