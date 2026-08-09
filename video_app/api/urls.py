"""URL routes for the video catalogue API."""

from django.urls import path

from video_app.api.views import VideoListView

urlpatterns = [
    path('video/', VideoListView.as_view(), name='video-list'),
]
