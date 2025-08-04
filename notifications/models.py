from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import BaseModel


class Notification(BaseModel):
    recipient = models.ForeignKey(
        'users.User',
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    verb = models.CharField(max_length=255)
    actor = models.ForeignKey(
        'users.User',
        null=True,
        blank=True,
        related_name='actor_notifications',
        on_delete=models.SET_NULL,
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')
    url = models.URLField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['recipient']),
            models.Index(fields=['is_read']),
            models.Index(fields=['timestamp']),
        ]
