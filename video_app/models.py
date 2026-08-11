"""Database models for categories and video catalogue entries."""

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def original_video_upload_to(instance, filename):
    """Store an upload under its stable video directory with a safe name."""
    extension = Path(filename).suffix.lower()
    return f'videos/{instance.storage_id}/original{extension}'


class Category(models.Model):
    """Represent a category that can be assigned to multiple videos."""

    class CategoryChoices(models.TextChoices):  # pylint: disable=too-many-ancestors
        """Define the category values supported by the application."""

        DRAMA = 'drama', 'Drama'
        ROMANCE = 'romance', 'Romance'

    name = models.CharField(
        max_length=100,
        choices=CategoryChoices.choices,
        unique=True,
    )

    def __str__(self):
        """Return the human-readable category label."""
        return self.get_name_display()  # type:ignore


class Video(models.Model):
    """Store a video catalogue entry and its processing metadata."""

    class ProcessingStatus(  # pylint: disable=too-many-ancestors
        models.TextChoices
    ):
        """Describe the asynchronous processing lifecycle."""

        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        READY = 'ready', 'Ready'
        FAILED = 'failed', 'Failed'

    storage_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    original = models.FileField(upload_to=original_video_upload_to, blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, editable=False)
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processing_error = models.TextField(blank=True, default='', editable=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='videos',
    )

    def __str__(self) -> str:
        """Return the video title as its human-readable representation."""
        return str(self.title)

    @property
    def output_directory(self):
        """Return the directory containing generated media for this video."""
        directory_name = str(self.storage_id) if self.original else str(self.pk)
        return Path(settings.MEDIA_ROOT) / 'videos' / directory_name

    @property
    def thumbnail_output_path(self):
        """Return the generated thumbnail path."""
        return self.output_directory / 'thumbnail.jpg'

    @property
    def master_playlist_path(self):
        """Return the generated multivariant playlist path."""
        return self.output_directory / 'master.m3u8'

    def variant_playlist_path(self, resolution):
        """Return a generated resolution playlist path."""
        return self.output_directory / resolution / 'index.m3u8'
