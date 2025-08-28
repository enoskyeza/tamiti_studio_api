
from rest_framework import viewsets, permissions
from .models import SocialPost, PostComment, SocialMetric, SocialPlatformProfile
from .serializers import (
    SocialPostSerializer,
    PostCommentSerializer,
    SocialMetricSerializer,
    SocialPlatformProfileSerializer,
)


class SocialPostViewSet(viewsets.ModelViewSet):
    queryset = SocialPost.objects.all().select_related('assigned_to', 'reviewer')
    serializer_class = SocialPostSerializer
    permission_classes = [permissions.IsAuthenticated]


class PostCommentViewSet(viewsets.ModelViewSet):
    queryset = PostComment.objects.all().select_related('post', 'author')
    serializer_class = PostCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class SocialMetricViewSet(viewsets.ModelViewSet):
    queryset = SocialMetric.objects.select_related('post')
    serializer_class = SocialMetricSerializer
    permission_classes = [permissions.IsAuthenticated]


class SocialPlatformProfileViewSet(viewsets.ModelViewSet):
    queryset = SocialPlatformProfile.objects.all()
    serializer_class = SocialPlatformProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
