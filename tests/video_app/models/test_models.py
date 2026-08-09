"""Tests for the video application's category and video models."""

from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from video_app.models import Category, Video

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_media_root(settings, tmp_path):
    """Keep uploaded test files outside the project's media directory."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def drama_category():
    """Create and return the supported drama category."""
    return Category.objects.create(name='drama')


def thumbnail_file(name='cover.jpg'):
    """Return an in-memory JPEG upload for thumbnail tests."""
    return SimpleUploadedFile(name, b'test-image-content', content_type='image/jpeg')


def create_video(category, **overrides):
    """Create a video with valid defaults and optional field overrides."""
    values = {
        'title': 'Movie Title',
        'description': 'Movie Description',
        'thumbnail': thumbnail_file(),
        'category': category,
    }
    values.update(overrides)
    return Video.objects.create(**values)


def test_category_name_is_unique_and_used_as_string_representation():
    """Use the display label for strings and reject duplicate names."""
    category = Category.objects.create(name='drama')

    assert str(category) == 'Drama'

    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.create(name='drama')


def test_category_name_is_limited_to_supported_choices():
    """Accept the configured choices and reject unsupported names."""
    assert Category.CategoryChoices.choices == [
        ('drama', 'Drama'),
        ('romance', 'Romance'),
    ]
    assert Category._meta.get_field('name').choices == (  # type:ignore
        Category.CategoryChoices.choices
    )

    category = Category(name='unsupported')

    with pytest.raises(ValidationError) as exc_info:
        category.full_clean()

    assert 'name' in exc_info.value.message_dict


def test_video_persists_documented_fields_and_thumbnail(drama_category, settings):
    """Persist all public video fields and store its thumbnail in media."""
    before_creation = timezone.now()

    video = create_video(drama_category)

    assert video.title == 'Movie Title'
    assert video.description == 'Movie Description'
    assert video.category == drama_category
    assert video.created_at >= before_creation
    assert video.created_at <= timezone.now()
    assert video.thumbnail.name == 'thumbnails/cover.jpg'
    assert Path(video.thumbnail.path).is_relative_to(settings.MEDIA_ROOT)
    assert Path(video.thumbnail.path).exists()
    assert str(video) == 'Movie Title'


def test_video_documented_fields_are_required():
    """Require every video field exposed by the documented response."""
    video = Video()

    with pytest.raises(ValidationError) as exc_info:
        video.full_clean()

    assert {'title', 'description', 'thumbnail', 'category'} <= set(
        exc_info.value.message_dict
    )


def test_category_exposes_related_videos(drama_category):
    """Expose videos through the category's reverse relationship."""
    video = create_video(drama_category)

    assert list(drama_category.videos.all()) == [video]


def test_video_category_can_be_reassigned(drama_category):
    """Allow correcting a video by assigning a different category."""
    video = create_video(drama_category)
    romance_category = Category.objects.create(name='romance')

    video.category = romance_category
    video.save(update_fields=['category'])
    video.refresh_from_db()

    assert video.category == romance_category
    assert not drama_category.videos.filter(pk=video.pk).exists()
    assert romance_category.videos.filter(pk=video.pk).exists()  # type:ignore


def test_category_in_use_cannot_be_deleted(drama_category):
    """Protect a category from deletion while a video references it."""
    video = create_video(drama_category)

    with pytest.raises(ProtectedError):
        drama_category.delete()

    assert Category.objects.filter(pk=drama_category.pk).exists()
    assert Video.objects.filter(pk=video.pk).exists()
