from django.apps import AppConfig


class VideoAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'video_app'

    def ready(self):
        """Register upload processing signals."""
        from video_app import signals  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import
