from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Comment
from .serializers import CommentSerializer


ALLOWED_TARGETS = {
    ('tasks', 'task'),
    ('projects', 'project'),
}


def _get_target(content_type_str: str, object_id: int, user):
    try:
        app_label, model = content_type_str.lower().split('.')
    except ValueError:
        raise ValidationError({'target_type': 'Invalid target_type. Use app_label.model'})
    if (app_label, model) not in ALLOWED_TARGETS:
        raise ValidationError({'target_type': 'Unsupported target type for now'})

    ct = get_object_or_404(ContentType, app_label=app_label, model=model)
    model_cls = ct.model_class()

    # Enforce access by created_by where available
    try:
        target = get_object_or_404(model_cls.objects.filter(created_by=user), pk=object_id)
    except Exception:
        # Fallback if created_by not present
        target = get_object_or_404(model_cls, pk=object_id)
        if hasattr(target, 'created_by') and target.created_by != user:
            raise PermissionDenied('Not allowed to access this target')
    return ct, target


class CommentListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    def get_queryset(self):
        # Required filters: target_type=app_label.model, target_id
        target_type = self.request.query_params.get('target_type')
        target_id = self.request.query_params.get('target_id')
        if not target_type or not target_id:
            raise ValidationError({'detail': 'target_type and target_id query params are required'})
        ct, target = _get_target(target_type, target_id, self.request.user)
        return Comment.objects.filter(
            content_type=ct,
            object_id=target.id,
            is_deleted=False
        ).select_related('author').order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentSerializer

    def get_queryset(self):
        # Only allow author to update/delete their comments; everyone else can read
        qs = Comment.objects.filter(is_deleted=False).select_related('author')
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            qs = qs.filter(author=self.request.user)
        return qs

    def perform_destroy(self, instance):
        # soft delete using BaseModel fields
        instance.soft_delete()

