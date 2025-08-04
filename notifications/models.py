from django.conf import settings
from django.db import models


class Notification(models.Model):
    LEVEL_CHOICES = [
        ("info", "Info"),
        ("alert", "Alert"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications",
        on_delete=models.CASCADE,
    )
    content = models.TextField()
    related_task = models.ForeignKey(
        "tasks.Task",
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")

    def __str__(self):
        return f"Notification to {self.user}: {self.content[:20]}"
