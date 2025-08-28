
from rest_framework import viewsets, permissions, filters
from .models import MediaAsset, MediaCategory
from .serializers import MediaAssetSerializer, MediaCategorySerializer
from django_filters.rest_framework import DjangoFilterBackend


class MediaAssetViewSet(viewsets.ModelViewSet):
    queryset = MediaAsset.objects.all().select_related('uploaded_by', 'category')
    serializer_class = MediaAssetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['title', 'description', 'alt_text', 'caption']
    filterset_fields = ['asset_type', 'category']
    ordering_fields = ['created_at', 'title']

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class MediaCategoryViewSet(viewsets.ModelViewSet):
    queryset = MediaCategory.objects.all()
    serializer_class = MediaCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
