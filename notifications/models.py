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
        related_name='actions',
        on_delete=models.SET_NULL,
    )
    recipient = models.ForeignKey(
        User,
        related_name='notifications',
        on_delete=models.CASCADE,
    )
    verb = models.CharField(max_length=255)
    target_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')
    url = models.URLField(blank=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.actor} {self.verb} {self.target}"
