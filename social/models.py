
from django.db import models
from django.utils import timezone
from core.models import BaseModel
from users.models import User
from common.enums import SocialPlatformType, PostStatus


class SocialPost(BaseModel):
    title = models.CharField(max_length=255)
    content_text = models.TextField()
    platform = models.CharField(max_length=50, choices=SocialPlatformType.choices)
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=30, choices=PostStatus.choices, default=PostStatus.DRAFT)
    assigned_to = models.ForeignKey(User, related_name='social_posts', on_delete=models.SET_NULL, null=True, blank=True)
    reviewer = models.ForeignKey(User, related_name='reviewed_posts', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} [{self.platform}]"


class PostComment(BaseModel):
    post = models.ForeignKey(SocialPost, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()

    def __str__(self):
        return f"Comment by {self.author} on {self.post.title}"


class SocialMetric(BaseModel):
    post = models.OneToOneField(SocialPost, related_name='metrics', on_delete=models.CASCADE)
    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    engagement_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    def calculate_score(self):
        score = self.likes * 0.4 + self.comments * 0.3 + self.shares * 0.2 + self.views * 0.1
        self.engagement_score = score
        self.save(update_fields=['engagement_score'])


class SocialPlatformProfile(BaseModel):
    platform = models.CharField(max_length=50, choices=SocialPlatformType.choices, unique=True)
    followers = models.PositiveIntegerField(default=0)
    posts_made = models.PositiveIntegerField(default=0)
    last_synced = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.platform} Profile"
