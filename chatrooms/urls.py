from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register(r'channels', views.ChannelViewSet, basename='channel')
router.register(r'channel-messages', views.ChannelMessageViewSet, basename='channel-message')
router.register(r'direct-threads', views.DirectThreadViewSet, basename='direct-thread')
router.register(r'direct-messages', views.DirectMessageViewSet, basename='direct-message')

urlpatterns = [
    path('', include(router.urls)),
]
