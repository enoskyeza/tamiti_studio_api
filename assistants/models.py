from django.db import models
from django.conf import settings

from core.models import BaseModel


class VACommand(BaseModel):
    assistant = models.ForeignKey("accounts.StaffRole", on_delete=models.CASCADE, related_name="commands")
    trigger_text = models.CharField(max_length=255, help_text="User command text")
    match_type = models.CharField(
        max_length=20,
        choices=[('exact', 'Exact'), ('contains', 'Contains')],
        default='exact'
    )
    response_mode = models.CharField(
        max_length=20,
        choices=[('text', 'Text'), ('api', 'API')],
        default='text'
    )
    response_text = models.TextField(blank=True, help_text="Fallback reply if text mode")
    api_endpoint = models.CharField(max_length=255, blank=True, help_text="API path to call if response_mode=api")
    requires_auth = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.assistant.title} → {self.trigger_text}"


class DefaultResponse(BaseModel):
    assistant = models.ForeignKey("accounts.StaffRole", on_delete=models.CASCADE, related_name="default_responses")
    fallback_text = models.TextField()
    condition = models.CharField(max_length=255, help_text="Optional keyword trigger or state", blank=True)

    def __str__(self):
        return f"Fallback for {self.assistant.title}"


class AssistantLog(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    assistant = models.ForeignKey("accounts.StaffRole", on_delete=models.SET_NULL, null=True)
    message_sent = models.TextField()
    response_text = models.TextField()
    used_gpt = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.assistant} log @ {self.timestamp}"
