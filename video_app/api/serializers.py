"""Serializers for the public video catalogue API."""

from rest_framework import serializers

from video_app.models import Video


class VideoListSerializer(serializers.ModelSerializer):
    """Serialize the read-only metadata exposed by the video list."""

    thumbnail_url = serializers.ImageField(source='thumbnail', read_only=True)
    category = serializers.CharField(
        source='category.get_name_display',
        read_only=True,
    )

    class Meta:
        """Define the endpoint's stable public response fields."""

        model = Video
        fields = (
            'id',
            'created_at',
            'title',
            'description',
            'thumbnail_url',
            'category',
        )
        read_only_fields = fields
