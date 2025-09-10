from django.urls import path

from .views import (
    CommentListCreateView, CommentDetailView, CommentReplyCreateView,
    search_users_for_mention, get_comment_replies, toggle_comment_internal
)


urlpatterns = [
    path('', CommentListCreateView.as_view(), name='comment-list-create'),
    path('<int:pk>/', CommentDetailView.as_view(), name='comment-detail'),
    path('<int:comment_id>/replies/', CommentReplyCreateView.as_view(), name='comment-reply-create'),
    path('<int:comment_id>/replies/list/', get_comment_replies, name='comment-replies-list'),
    path('<int:comment_id>/toggle-internal/', toggle_comment_internal, name='comment-toggle-internal'),
    path('search-users/', search_users_for_mention, name='search-users-for-mention'),
]

