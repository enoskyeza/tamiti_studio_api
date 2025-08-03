
from rest_framework import serializers
from .models import MediaAsset, MediaCategory


class MediaCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaCategory
        fields = '__all__'


class MediaAssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = MediaAsset
        fields = '__all__'
        read_only_fields = ('uploaded_by',)
