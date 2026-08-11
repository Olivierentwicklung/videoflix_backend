"""URL routes for the video catalogue API."""

from django.urls import path, re_path

from video_app.api.views import (
    VideoListView,
    VideoManifestView,
    VideoMasterManifestView,
    VideoSegmentView,
)

urlpatterns = [
    path('video/', VideoListView.as_view(), name='video-list'),
    path(
        'video/<int:movie_id>/master.m3u8',
        VideoMasterManifestView.as_view(),
        name='video-master-manifest',
    ),
    path(
        'video/<int:movie_id>/<str:resolution>/index.m3u8',
        VideoManifestView.as_view(),
        name='video-manifest',
    ),
    re_path(
        r'^video/(?P<movie_id>\d+)/(?P<resolution>[^/]+)/(?P<segment>[^/]+)/?$',
        VideoSegmentView.as_view(),
        name='video-segment',
    ),
]
