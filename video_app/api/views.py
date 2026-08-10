"""Views for the video catalogue API."""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from video_app.api.schema.base_schema import (
    VIDEO_TAG,
)
from video_app.api.schema.list_videos_schema import (
    VIDEO_LIST_DESCRIPTION,
    VIDEO_LIST_RESPONSES,
)
from video_app.api.schema.video_manifest_schema import (
    VIDEO_MANIFEST_DESCRIPTION,
    VIDEO_MANIFEST_PARAMETERS,
    VIDEO_MANIFEST_RESPONSES,
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


class VideoManifestView(APIView):
    """Stream a prebuilt HLS manifest to an authenticated user."""

    permission_classes = [IsAuthenticated]
    throttle_classes = []
    supported_resolutions = frozenset({'480p', '720p', '1080p'})

    @extend_schema(
        tags=VIDEO_TAG,
        summary='HLS-Master-Playlist abrufen',
        description=VIDEO_MANIFEST_DESCRIPTION,
        parameters=VIDEO_MANIFEST_PARAMETERS,
        request=None,
        responses=VIDEO_MANIFEST_RESPONSES,
    )
    def get(self, request, movie_id: int, resolution: str):
        """Return the requested manifest when its video and file exist."""
        del request

        if resolution not in self.supported_resolutions:
            raise NotFound()

        if not Video.objects.filter(pk=movie_id).exists():
            raise NotFound()

        manifest_path = (
            Path(settings.MEDIA_ROOT)
            / 'videos'
            / str(movie_id)
            / resolution
            / 'index.m3u8'
        )
        if not manifest_path.is_file():
            raise NotFound()

        return FileResponse(
            manifest_path.open('rb'),
            content_type='application/vnd.apple.mpegurl',
        )
