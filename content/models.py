
from django.db import models
from django.contrib.auth import get_user_model
from core.models import BaseModel
from common.enums import AssetType

User = get_user_model()


class MediaCategory(BaseModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class MediaAsset(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    caption = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    asset_type = models.CharField(max_length=50, choices=AssetType.choices, default=AssetType.PHOTO)
    file = models.FileField(upload_to="uploads/media_assets/", blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
    size = models.CharField(max_length=20, blank=True)  # e.g., '2.4 MB'
    dimensions = models.CharField(max_length=20, blank=True)  # e.g., '1920x1080'
    category = models.ForeignKey(MediaCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_assets")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title
