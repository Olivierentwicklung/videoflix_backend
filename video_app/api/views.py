"""Views for the video catalogue API."""

import re

from django.http import FileResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from video_app.api.constants import (
    HLS_MANIFEST_CONTENT_TYPE,
    HLS_SEGMENT_CONTENT_TYPE,
    SUPPORTED_VIDEO_RESOLUTIONS,
)
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
from video_app.api.schema.video_segment_schema import (
    VIDEO_SEGMENT_DESCRIPTION,
    VIDEO_SEGMENT_PARAMETERS,
    VIDEO_SEGMENT_RESPONSES,
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
    supported_resolutions = frozenset(SUPPORTED_VIDEO_RESOLUTIONS)

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

        try:
            video = Video.objects.get(pk=movie_id)
        except Video.DoesNotExist:
            raise NotFound() from None

        manifest_path = video.variant_playlist_path(resolution)
        if not manifest_path.is_file():
            raise NotFound()

        return FileResponse(
            manifest_path.open('rb'),
            content_type=HLS_MANIFEST_CONTENT_TYPE,
        )


class VideoMasterManifestView(APIView):
    """Stream a generated HLS multivariant playlist."""

    permission_classes = [IsAuthenticated]
    throttle_classes = []

    @extend_schema(
        tags=VIDEO_TAG,
        summary='HLS-Master-Playlist abrufen',
        request=None,
        responses=VIDEO_MANIFEST_RESPONSES,
    )
    def get(self, request, movie_id: int):
        """Return the master manifest when its ready file exists."""
        del request
        try:
            video = Video.objects.get(pk=movie_id)
        except Video.DoesNotExist:
            raise NotFound() from None
        manifest_path = video.master_playlist_path
        if not manifest_path.is_file():
            raise NotFound()
        return FileResponse(
            manifest_path.open('rb'),
            content_type=HLS_MANIFEST_CONTENT_TYPE,
        )


class VideoSegmentView(APIView):
    """Stream a prebuilt HLS video segment to an authenticated user."""

    permission_classes = [IsAuthenticated]
    throttle_classes = []
    supported_resolutions = frozenset(SUPPORTED_VIDEO_RESOLUTIONS)
    segment_filename_pattern = re.compile(r'(?:segment_)?[0-9]+\.ts')

    @extend_schema(
        tags=VIDEO_TAG,
        summary='HLS-Videosegment abrufen',
        description=VIDEO_SEGMENT_DESCRIPTION,
        parameters=VIDEO_SEGMENT_PARAMETERS,
        request=None,
        responses=VIDEO_SEGMENT_RESPONSES,
    )
    def get(
        self,
        request,
        movie_id: int,
        resolution: str,
        segment: str,
    ):
        """Return the requested segment when its video and file exist."""
        del request

        if resolution not in self.supported_resolutions:
            raise NotFound()

        if self.segment_filename_pattern.fullmatch(segment) is None:
            raise NotFound()

        try:
            video = Video.objects.get(pk=movie_id)
        except Video.DoesNotExist:
            raise NotFound() from None

        segment_path = video.output_directory / resolution / segment
        if not segment_path.is_file():
            raise NotFound()

        try:
            segment_file = segment_path.open('rb')
        except OSError:
            raise NotFound() from None

        return FileResponse(
            segment_file,
            content_type=HLS_SEGMENT_CONTENT_TYPE,
        )
