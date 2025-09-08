import re
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

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

    # threading (limited to 1 level)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        related_name='replies',
        on_delete=models.CASCADE
    )

    # mentions
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='mentioned_in_comments'
    )

    # generic target
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # optional flag similar to ProjectComment
    is_internal = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validate that replies are only 1 level deep"""
        if self.parent and self.parent.parent:
            raise ValidationError("Comments can only be nested 1 level deep")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
        # Extract mentions from content after saving
        if self.pk:
            self.extract_mentions()

    def extract_mentions(self):
        """Extract @mentions from comment content and add to mentioned_users"""
        from users.models import User
        
        # Find all @mentions in the content
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, self.content)
        
        if mentions:
            # Find users by username or email
            mentioned_users = User.objects.filter(
                models.Q(username__in=mentions) | models.Q(email__in=mentions)
            )
            self.mentioned_users.set(mentioned_users)

    @property
    def is_reply(self):
        """Check if this comment is a reply to another comment"""
        return self.parent is not None

    @property
    def reply_count(self):
        """Get count of replies to this comment"""
        return self.replies.count()

    @property
    def thread_root(self):
        """Get the root comment of this thread"""
        return self.parent if self.parent else self

    def __str__(self) -> str:  # pragma: no cover - simple representation
        target = f"{self.content_type.app_label}.{self.content_type.model}:{self.object_id}"
        reply_indicator = " (Reply)" if self.is_reply else ""
        return f"Comment({self.id}) by {self.author_id} on {target}{reply_indicator}"

