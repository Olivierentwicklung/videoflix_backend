"""Tests for development-only uploaded-media serving."""

from django.test import override_settings
from django.urls import resolve

from core.urls import development_media_urlpatterns


@override_settings(DEBUG=True, MEDIA_URL='/media/', MEDIA_ROOT='/tmp/test-media')
def test_development_media_urlpatterns_resolve_uploaded_files():
    """Route MEDIA_URL paths through Django while developing locally."""
    patterns = development_media_urlpatterns()

    match = resolve('/media/videos/example/thumbnail.jpg', urlconf=tuple(patterns))

    assert match.kwargs['path'] == 'videos/example/thumbnail.jpg'
    assert match.kwargs['document_root'] == '/tmp/test-media'


@override_settings(DEBUG=False)
def test_development_media_urlpatterns_are_disabled_in_production():
    """Leave production media delivery to the deployment web server."""
    assert development_media_urlpatterns() == []
