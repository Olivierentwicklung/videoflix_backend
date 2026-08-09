"""Contract tests for the authenticated video-list endpoint."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from video_app.models import Category, Video

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def temporary_media_root(settings, tmp_path):
    """Keep uploaded thumbnails outside the project's media directory."""
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
def authenticated_client(user):
    """Return an API client authenticated with a real JWT access token."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.fixture
def categories():
    """Create the categories used by the endpoint response tests."""
    return {
        'drama': Category.objects.create(name=Category.CategoryChoices.DRAMA),
        'romance': Category.objects.create(name=Category.CategoryChoices.ROMANCE),
    }


def create_video(category, *, thumbnail_name='cover.jpg', **overrides):
    """Create a video with valid defaults and an isolated thumbnail."""
    values = {
        'title': 'Movie Title',
        'description': 'Movie Description',
        'thumbnail': SimpleUploadedFile(
            thumbnail_name,
            b'test-image-content',
            content_type='image/jpeg',
        ),
        'category': category,
    }
    values.update(overrides)
    return Video.objects.create(**values)


def test_video_list_requires_jwt_authentication():
    """Reject requests that do not provide a valid access JWT."""
    response = APIClient().get('/api/video/')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED  # type:ignore


def test_video_list_returns_all_documented_metadata(
    authenticated_client,
    categories,
):
    """Return every video using the documented public response shape."""
    video = create_video(categories['drama'])

    response = authenticated_client.get(reverse('video-list'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0] == {
        'id': video.pk,
        'created_at': response.data[0]['created_at'],
        'title': 'Movie Title',
        'description': 'Movie Description',
        'thumbnail_url': 'http://testserver/media/thumbnails/cover.jpg',
        'category': 'Drama',
    }
    assert parse_datetime(response.data[0]['created_at']) == video.created_at


def test_video_list_returns_an_empty_list(authenticated_client):
    """Return a successful empty collection when no videos exist."""
    response = authenticated_client.get(reverse('video-list'))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


def test_video_list_has_stable_oldest_first_ordering(
    authenticated_client,
    categories,
):
    """Order videos deterministically by creation time and primary key."""
    first = create_video(
        categories['drama'],
        title='First Movie',
        thumbnail_name='first.jpg',
    )
    second = create_video(
        categories['romance'],
        title='Second Movie',
        thumbnail_name='second.jpg',
    )
    shared_created_at = timezone.now() - timedelta(days=1)
    Video.objects.filter(pk__in=[first.pk, second.pk]).update(
        created_at=shared_created_at
    )
    latest = create_video(
        categories['drama'],
        title='Latest Movie',
        thumbnail_name='latest.jpg',
    )

    response = authenticated_client.get(reverse('video-list'))

    assert response.status_code == status.HTTP_200_OK
    assert [item['id'] for item in response.data] == [
        first.pk,
        second.pk,
        latest.pk,
    ]


def test_video_list_rejects_unsupported_methods(authenticated_client):
    """Expose the collection as a read-only endpoint."""
    response = authenticated_client.post(reverse('video-list'), {}, format='json')

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_video_list_permission_and_rate_limit_contract():
    """Keep authentication required and this endpoint explicitly unthrottled."""
    view_class = resolve('/api/video/').func.view_class  # type:ignore

    assert view_class.permission_classes == [IsAuthenticated]
    assert view_class.throttle_classes == []


def test_video_list_avoids_category_n_plus_one_queries(
    authenticated_client,
    categories,
    django_assert_num_queries,
):
    """Fetch any number of videos and their categories in one catalogue query."""
    create_video(categories['drama'], thumbnail_name='one.jpg')
    create_video(categories['romance'], thumbnail_name='two.jpg')
    create_video(categories['drama'], thumbnail_name='three.jpg')

    with django_assert_num_queries(2):
        response = authenticated_client.get(reverse('video-list'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3
