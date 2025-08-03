from django.urls import path, include
from rest_framework.routers import DefaultRouter
from content.views_content import MediaItemViewSet, MediaCategoryViewSet

router = DefaultRouter()
router.register(r'categories', MediaCategoryViewSet)
router.register(r'media', MediaItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
