from django.conf import settings
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


from core.models import BaseModel
from users.models import User


class Notification(BaseModel):
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name='actor_notifications',
        on_delete=models.SET_NULL,
    )
    recipient = models.ForeignKey(
        User,
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    verb = models.CharField(max_length=255)

    # Generic relation to the target object
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")
    url = models.URLField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.actor} {self.verb} {self.target}"
