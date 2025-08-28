from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from accounts.models import StaffRole
from .services import process_va_chat
from .serializers import AssistantChatSerializer, AssistantResponseSerializer


class AssistantChatView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssistantChatSerializer

    @extend_schema(responses=AssistantResponseSerializer)
    def post(self, request, assistant_id):
        assistant = get_object_or_404(StaffRole, pk=assistant_id, is_virtual=True)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_input = serializer.validated_data["message"]

        response = process_va_chat(assistant, user_input, user=request.user)

        response_data = AssistantResponseSerializer({
            "assistant": assistant.title,
            "response": response,
        }).data

        return Response(response_data)
