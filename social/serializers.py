
from rest_framework import serializers
from .models import SocialPost, PostComment, SocialMetric, SocialPlatformProfile


class PostCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = PostComment
        fields = '__all__'
        read_only_fields = ('author',)


class SocialMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMetric
        fields = '__all__'


class SocialPostSerializer(serializers.ModelSerializer):
    comments = PostCommentSerializer(many=True, read_only=True)
    metrics = SocialMetricSerializer(read_only=True)

    class Meta:
        model = SocialPost
        fields = '__all__'
        read_only_fields = ('approved_at',)


class SocialPlatformProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialPlatformProfile
        fields = '__all__'
