from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from core.models import BaseModel
from django.conf import settings


class Comment(BaseModel):
    """Global comments linked to any model via GenericForeignKey."""

    # author and content
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField()

    # threading
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        related_name='replies',
        on_delete=models.CASCADE
    )

    # generic target
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # optional flag similar to ProjectComment
    is_internal = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:  # pragma: no cover - simple representation
        target = f"{self.content_type.app_label}.{self.content_type.model}:{self.object_id}"
        return f"Comment({self.id}) by {self.author_id} on {target}"

