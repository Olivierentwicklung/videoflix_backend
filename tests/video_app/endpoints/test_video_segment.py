"""Contract tests for the authenticated HLS video-segment endpoint."""

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

SEGMENT_CONTENT = b'\x47\x40\x00\x10test-mpeg-ts-payload'
SUPPORTED_RESOLUTIONS = ('480p', '720p', '1080p')


@pytest.fixture(autouse=True)
def temporary_media_root(settings, tmp_path):
    """Keep segment and thumbnail files outside the project media directory."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def user():
    """Create an active user allowed to request protected video segments."""
    return User.objects.create_user(  # type:ignore
        username='viewer@example.com',
        email='viewer@example.com',
        password='securepassword',
    )


@pytest.fixture
def access_token(user):
    """Return a valid access JWT for endpoint authentication tests."""
    return str(AccessToken.for_user(user))


@pytest.fixture
def authenticated_client(access_token):
    """Return an API client authenticated through a Bearer JWT."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return client


@pytest.fixture
def video():
    """Create a video whose segments can be requested."""
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


def segment_url(movie_id, resolution='720p', segment='000.ts'):
    """Build the public URL for one HLS video segment."""
    return reverse(
        'video-segment',
        kwargs={
            'movie_id': movie_id,
            'resolution': resolution,
            'segment': segment,
        },
    )


def write_segment(
    movie_id,
    resolution='720p',
    segment='000.ts',
    content=SEGMENT_CONTENT,
):
    """Create a prebuilt segment using the endpoint's storage contract."""
    segment_path = (
        Path(settings.MEDIA_ROOT) / 'videos' / str(movie_id) / resolution / segment
    )
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    segment_path.write_bytes(content)
    return segment_path


def response_body(response):
    """Consume a streaming response and return its byte content."""
    return b''.join(response.streaming_content)


def test_video_segment_returns_stored_binary_file(authenticated_client, video):
    """Stream the requested segment verbatim with the MPEG-TS media type."""
    write_segment(video.pk)

    response = authenticated_client.get(segment_url(video.pk))

    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Type'] == 'video/MP2T'
    assert response_body(response) == SEGMENT_CONTENT


def test_video_segment_supports_configured_jwt_cookie(video, access_token):
    """Authenticate segment requests through the configured access cookie."""
    write_segment(video.pk)
    client = APIClient()
    client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = access_token

    response = client.get(segment_url(video.pk))

    assert response.status_code == status.HTTP_200_OK  # type:ignore
    assert response_body(response) == SEGMENT_CONTENT


def test_video_segment_requires_jwt_authentication(video):
    """Reject requests without a valid access JWT."""
    write_segment(video.pk)

    response = APIClient().get(segment_url(video.pk))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # type:ignore


def test_video_segment_returns_404_for_unknown_video(authenticated_client):
    """Require a database video even when a matching segment exists."""
    missing_movie_id = 999
    write_segment(missing_movie_id)

    response = authenticated_client.get(segment_url(missing_movie_id))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_segment_returns_404_when_file_is_missing(
    authenticated_client,
    video,
):
    """Return not found when the requested segment does not exist."""
    response = authenticated_client.get(segment_url(video.pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_segment_returns_404_when_path_is_not_a_file(
    authenticated_client,
    video,
):
    """Reject a directory located where the segment file should be."""
    segment_path = (
        Path(settings.MEDIA_ROOT) / 'videos' / str(video.pk) / '720p' / '000.ts'
    )
    segment_path.mkdir(parents=True)

    response = authenticated_client.get(segment_url(video.pk))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_segment_returns_404_for_unsupported_resolution(
    authenticated_client,
    video,
):
    """Reject resolution directory names outside the public allowlist."""
    write_segment(video.pk, resolution='2160p')

    response = authenticated_client.get(segment_url(video.pk, resolution='2160p'))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize('resolution', SUPPORTED_RESOLUTIONS)
def test_video_segment_supports_each_documented_resolution(
    authenticated_client,
    video,
    resolution,
):
    """Resolve every documented resolution from its independent directory."""
    content = f'{resolution}-segment'.encode()
    write_segment(video.pk, resolution=resolution, content=content)

    response = authenticated_client.get(segment_url(video.pk, resolution=resolution))

    assert response.status_code == status.HTTP_200_OK
    assert response_body(response) == content


@pytest.mark.parametrize(
    'invalid_segment',
    ('segment.ts', '000.m4s', '000.ts.bak', '.ts'),
)
def test_video_segment_returns_404_for_invalid_segment_filename(
    authenticated_client,
    video,
    invalid_segment,
):
    """Accept only numeric MPEG-TS segment filenames."""
    response = authenticated_client.get(segment_url(video.pk, segment=invalid_segment))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_video_segment_blocks_windows_style_path_traversal(
    authenticated_client,
    video,
):
    """Do not treat a URL-encoded backslash as a filesystem separator."""
    escaped_content = b'content-outside-resolution-directory'
    write_segment(video.pk, resolution='', segment='secret.ts', content=escaped_content)
    traversal_url = f'/api/video/{video.pk}/720p/..%5Csecret.ts/'

    response = authenticated_client.get(traversal_url)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not getattr(response, 'streaming', False)


def test_video_segment_rejects_unsupported_methods(authenticated_client, video):
    """Expose video segments through read-only HTTP methods."""
    write_segment(video.pk)

    response = authenticated_client.post(segment_url(video.pk), {}, format='json')

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_video_segment_permission_and_rate_limit_contract():
    """Keep JWT authentication required and this endpoint unthrottled."""
    view_class = resolve('/api/video/1/720p/000.ts/').func.view_class  # type:ignore

    assert view_class.permission_classes == [IsAuthenticated]
    assert view_class.throttle_classes == []
