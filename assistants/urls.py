from django.urls import path
from assistants.views import AssistantChatView

urlpatterns = [
    path('chat/<int:assistant_id>/', AssistantChatView.as_view(), name='assistant-chat'),
]
