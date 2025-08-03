from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from accounts.models import StaffRole
from .services import process_va_chat
from .serializers import AssistantChatSerializer, AssistantResponseSerializer


class AssistantChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, assistant_id):
        assistant = get_object_or_404(StaffRole, pk=assistant_id, is_virtual=True)
        serializer = AssistantChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_input = serializer.validated_data["message"]

        response = process_va_chat(assistant, user_input, user=request.user)

        response_data = AssistantResponseSerializer({
            "assistant": assistant.title,
            "response": response
        }).data

        return Response(response_data)