"""Views for the video catalogue API."""

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from video_app.api.serializers import VideoListSerializer
from video_app.models import Video


class VideoListView(ListAPIView):
    """Return all available videos to authenticated users."""

    serializer_class = VideoListSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = []
    queryset = Video.objects.select_related('category').order_by('created_at', 'pk')
