
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SocialPostViewSet,
    PostCommentViewSet,
    SocialMetricViewSet,
    SocialPlatformProfileViewSet
)

router = DefaultRouter()
router.register(r'posts', SocialPostViewSet)
router.register(r'comments', PostCommentViewSet)
router.register(r'metrics', SocialMetricViewSet)
router.register(r'platforms', SocialPlatformProfileViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
