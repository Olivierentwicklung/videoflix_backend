"""URL routes for the video catalogue API."""

from django.urls import path

from video_app.api.views import VideoListView, VideoManifestView

urlpatterns = [
    path('video/', VideoListView.as_view(), name='video-list'),
    path(
        'video/<int:movie_id>/<str:resolution>/index.m3u8',
        VideoManifestView.as_view(),
        name='video-manifest',
    ),
]
