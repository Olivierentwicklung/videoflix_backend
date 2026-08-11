"""Tests for the video application's Django admin configuration."""

from django.contrib import admin

from video_app.admin import VideoAdminForm
from video_app.models import Category, Video


def test_category_and_video_are_registered():
    """Register both catalogue models with the default admin site."""
    assert admin.site.is_registered(Category)
    assert admin.site.is_registered(Video)


def test_category_admin_configuration():
    """Provide useful category columns, search, and alphabetical ordering."""
    category_admin = admin.site._registry[Category]

    assert category_admin.list_display == ('id', 'name')
    assert category_admin.search_fields == ('name',)
    assert category_admin.ordering == ('name',)


def test_video_admin_configuration():
    """Provide efficient video listing, filtering, search, and ordering."""
    video_admin = admin.site._registry[Video]

    assert video_admin.form is VideoAdminForm
    assert video_admin.list_display == (
        'id',
        'title',
        'category',
        'processing_status',
        'created_at',
    )
    assert video_admin.list_filter == ('category', 'processing_status', 'created_at')
    assert video_admin.search_fields == ('title', 'description')
    assert video_admin.ordering == ('-created_at',)
    assert video_admin.list_select_related == ('category',)
    assert video_admin.readonly_fields == (
        'storage_id',
        'thumbnail',
        'processing_status',
        'processing_error',
    )


def test_video_admin_requires_original_for_new_video():
    """Require a source upload when creating a catalogue entry."""
    form = VideoAdminForm(
        data={
            'title': 'Movie',
            'description': 'Description',
            'category': '',
        }
    )

    assert not form.is_valid()
    assert 'original' in form.errors
