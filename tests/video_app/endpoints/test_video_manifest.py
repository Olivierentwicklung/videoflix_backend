"""Contract tests for the authenticated HLS manifest endpoint."""

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve, reverse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from video_app.models import Category, Video

pytestmark = pytest.mark.django_db

User = get_user_model()

MANIFEST_CONTENT = b'#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-ENDLIST\n'
SUPPORTED_RESOLUTIONS = ('480p', '720p', '1080p')


@pytest.fixture(autouse=True)
def temporary_media_root(settings, tmp_path):
    """Keep manifest and thumbnail files outside the project media directory."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def user():
    """Create an active user allowed to request the protected endpoint."""
    return User.objects.create_user(  # type:ignore
        username='viewer@example.com',
        email='viewer@example.com',
        password='securepassword',
    )


@pytest.fixture
def access_token(user):
    """Return a valid access JWT for the endpoint authentication tests."""
    return str(AccessToken.for_user(user))


@pytest.fixture
def authenticated_client(access_token):
    """Return an API client authenticated through a Bearer JWT."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return client


@pytest.fixture
def video():
    """Create a video whose manifest can be requested."""
    category = Category.objects.create(name=Category.CategoryChoices.DRAMA)
    return Video.objects.create(
        title='Movie Title',
        description='Movie Description',
        thumbnail=SimpleUploadedFile(
            'cover.jpg',
            b'test-image-content',
            content_type='image/jpeg',
        ),
        category=category,
    )


def manifest_url(movie_id, resolution='720p'):
    """Build the public URL for one video's resolution manifest."""
    return reverse(
        'video-manifest',
        kwargs={'movie_id': movie_id, 'resolution': resolution},
    )


def write_manifest(movie_id, resolution='720p', content=MANIFEST_CONTENT):
    """Create a prebuilt manifest using the endpoint's storage contract."""
    manifest_path = (
        Path(settings.MEDIA_ROOT) / 'videos' / str(movie_id) / resolution / 'index.m3u8'
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(content)
    return manifest_path


def response_body(response):
    """Consume a streaming response and return its byte content."""
    return b''.join(response.streaming_content)


def test_video_manifest_returns_stored_file(authenticated_client, video):
    """Stream the requested manifest verbatim with the HLS media type."""
    write_manifest(video.pk)

    response = authenticated_client.get(manifest_url(video.pk))

    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Type'] == 'application/vnd.apple.mpegurl'
    assert response_body(response) == MANIFEST_CONTENT


def test_video_manifest_supports_configured_jwt_cookie(video, access_token):
    """Authenticate manifest requests through the configured access cookie."""
    write_manifest(video.pk)
    client = APIClient()
    client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = access_token

    response = client.get(manifest_url(video.pk))

    assert response.status_code == status.HTTP_200_OK  # type:ignore
    assert response_body(response) == MANIFEST_CONTENT


def test_video_manifest_requires_jwt_authentication(video):
    """Reject requests without a valid access JWT."""
    write_manifest(video.pk)

    response = APIClient().get(manifest_url(video.pk))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # type:ignore


def test_video_manifest_returns_404_for_unknown_video(authenticated_client):
    """Require a database video even when a matching manifest exists."""
    missing_movie_id = 999
    write_manifest(missing_movie_id)

    response = authenticated_client.get(manifest_url(missing_movie_id))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_manifest_returns_404_when_file_is_missing(
    authenticated_client,
    video,
):
    """Return not found when the video has no manifest for that resolution."""
    response = authenticated_client.get(manifest_url(video.pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_manifest_returns_404_when_path_is_not_a_file(
    authenticated_client,
    video,
):
    """Reject a directory located where the manifest file should be."""
    manifest_path = write_manifest(video.pk)
    manifest_path.unlink()
    manifest_path.mkdir()

    response = authenticated_client.get(manifest_url(video.pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_manifest_returns_404_for_unsupported_resolution(
    authenticated_client,
    video,
):
    """Reject resolution directory names outside the public allowlist."""
    write_manifest(video.pk, resolution='2160p')

    response = authenticated_client.get(manifest_url(video.pk, '2160p'))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize('resolution', SUPPORTED_RESOLUTIONS)
def test_video_manifest_supports_each_documented_resolution(
    authenticated_client,
    video,
    resolution,
):
    """Resolve every documented resolution from its independent directory."""
    content = f'#EXTM3U\n# {resolution}\n'.encode()
    write_manifest(video.pk, resolution=resolution, content=content)

    response = authenticated_client.get(manifest_url(video.pk, resolution))

    assert response.status_code == status.HTTP_200_OK
    assert response_body(response) == content


def test_video_manifest_rejects_unsupported_methods(authenticated_client, video):
    """Expose manifests through read-only HTTP methods."""
    write_manifest(video.pk)

    response = authenticated_client.post(manifest_url(video.pk), {}, format='json')

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_video_manifest_permission_and_rate_limit_contract():
    """Keep JWT authentication required and this endpoint unthrottled."""
    view_class = resolve('/api/video/1/720p/index.m3u8').func.view_class  # type:ignore

    assert view_class.permission_classes == [IsAuthenticated]
    assert view_class.throttle_classes == []
