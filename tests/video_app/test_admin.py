"""Tests for the video application's Django admin configuration."""

from django.contrib import admin

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

    assert video_admin.list_display == ('id', 'title', 'category', 'created_at')
    assert video_admin.list_filter == ('category', 'created_at')
    assert video_admin.search_fields == ('title', 'description')
    assert video_admin.ordering == ('-created_at',)
    assert video_admin.list_select_related == ('category',)
