from django.db import models
from users.models import User

class DashboardWidget(models.Model):
    """Optional: allows users to customize their dashboard layout or widgets."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dashboard_widgets")
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.user.email} - {self.name}"