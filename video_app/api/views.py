"""Views for the video catalogue API."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from video_app.api.schema.base_schema import (
    VIDEO_TAG,
)
from video_app.api.schema.list_videos_schema import (
    VIDEO_LIST_DESCRIPTION,
    VIDEO_LIST_RESPONSES,
)
from video_app.api.serializers import VideoListSerializer
from video_app.models import Video


@extend_schema_view(
    get=extend_schema(
        tags=VIDEO_TAG,
        summary='Alle verfügbaren Videos auflisten',
        description=VIDEO_LIST_DESCRIPTION,
        request=None,
        responses=VIDEO_LIST_RESPONSES,
    )
)
class VideoListView(ListAPIView):
    """Return all available videos to authenticated users."""

    serializer_class = VideoListSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = []
    queryset = Video.objects.select_related('category').order_by('created_at', 'pk')
