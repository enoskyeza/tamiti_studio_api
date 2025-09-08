from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Comment
from .serializers import CommentSerializer, CommentReplySerializer, MentionSearchSerializer, UserMentionSerializer
from users.models import User


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
        
        # Only return top-level comments (not replies)
        return Comment.objects.filter(
            content_type=ct,
            object_id=target.id,
            is_deleted=False,
            parent__isnull=True  # Only top-level comments
        ).select_related('author').prefetch_related('replies', 'mentioned_users').order_by('-created_at')

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


class CommentReplyCreateView(generics.CreateAPIView):
    """Create a reply to a specific comment"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentReplySerializer

    def perform_create(self, serializer):
        parent_id = self.kwargs['comment_id']
        parent_comment = get_object_or_404(Comment, id=parent_id, is_deleted=False)
        
        # Ensure we're not replying to a reply (1 level deep only)
        if parent_comment.parent:
            raise ValidationError("Cannot reply to a reply. Comments can only be nested 1 level deep.")
        
        serializer.save(
            author=self.request.user,
            parent=parent_comment,
            content_type=parent_comment.content_type,
            object_id=parent_comment.object_id
        )


@extend_schema(
    parameters=[
        OpenApiParameter(name="query", type=str, location=OpenApiParameter.QUERY, description="Search query for users")
    ],
    responses=UserMentionSerializer(many=True),
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_users_for_mention(request):
    """Search users for @mention functionality"""
    query = request.query_params.get('query', '').strip()
    
    if len(query) < 2:
        return Response({'detail': 'Query must be at least 2 characters'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Search users by username, email, first_name, last_name
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(email__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]  # Limit to 10 results
    
    user_data = []
    for user in users:
        user_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'avatar': getattr(user, 'avatar', None)
        })
    
    return Response(user_data)


@extend_schema(
    parameters=[OpenApiParameter(name="comment_id", type=int, location=OpenApiParameter.PATH)],
    responses=CommentReplySerializer(many=True),
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_comment_replies(request, comment_id):
    """Get all replies for a specific comment"""
    parent_comment = get_object_or_404(Comment, id=comment_id, is_deleted=False)
    
    replies = Comment.objects.filter(
        parent=parent_comment,
        is_deleted=False
    ).select_related('author').prefetch_related('mentioned_users').order_by('created_at')
    
    serializer = CommentReplySerializer(replies, many=True)
    return Response(serializer.data)


@extend_schema(
    parameters=[OpenApiParameter(name="comment_id", type=int, location=OpenApiParameter.PATH)],
    responses=CommentSerializer,
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_comment_internal(request, comment_id):
    """Toggle the internal status of a comment"""
    comment = get_object_or_404(Comment, id=comment_id, author=request.user, is_deleted=False)
    
    comment.is_internal = not comment.is_internal
    comment.save()
    
    serializer = CommentSerializer(comment)
    return Response(serializer.data)

