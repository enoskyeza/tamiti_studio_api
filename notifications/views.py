from rest_framework import viewsets, permissions, decorators, response
from django_filters.rest_framework import DjangoFilterBackend
from common.pagination import DefaultPagination

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'is_read': ['exact'],
        'created_at': ['gte', 'lte'],
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        return (
            Notification.objects.filter(recipient=self.request.user)
            .select_related('actor', 'content_type')
        )

    @decorators.action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return response.Response({'status': 'marked read'})

    @decorators.action(detail=True, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = False
        notification.save(update_fields=['is_read'])
        return response.Response({'status': 'marked unread'})

    @decorators.action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return response.Response({'updated': updated})
