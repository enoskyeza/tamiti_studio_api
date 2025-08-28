from django.urls import path, include
from rest_framework.routers import DefaultRouter
from content.views import MediaAssetViewSet, MediaCategoryViewSet

router = DefaultRouter()
router.register(r'categories', MediaCategoryViewSet)
router.register(r'media', MediaAssetViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
