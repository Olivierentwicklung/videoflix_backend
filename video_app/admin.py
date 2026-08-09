"""Django admin configuration for the video catalogue."""

from django.contrib import admin

from video_app.models import Category, Video


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Configure category management in the Django admin."""

    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Configure efficient video management in the Django admin."""

    list_display = ('id', 'title', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
    list_select_related = ('category',)
