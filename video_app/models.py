"""Database models for categories and video catalogue entries."""

from django.db import models


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
    """Store a video catalogue entry and its thumbnail metadata."""

    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to='thumbnails/')
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='videos',
    )

    def __str__(self) -> str:
        """Return the video title as its human-readable representation."""
        return str(self.title)
