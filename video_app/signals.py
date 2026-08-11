"""Signals connecting stored uploads to the existing RQ worker."""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_rq import get_queue

from video_app.models import Video
from video_app.tasks import ERROR_LIMIT, process_video

LOGGER = logging.getLogger(__name__)


def enqueue_video_processing(video_id):
    """Submit a processing job and record infrastructure failures."""
    try:
        get_queue('default').enqueue(process_video, video_id)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        LOGGER.exception('Unable to enqueue processing for video %s', video_id)
        Video.objects.filter(pk=video_id).update(
            processing_status=Video.ProcessingStatus.FAILED,
            processing_error=str(exc)[-ERROR_LIMIT:],
        )


@receiver(pre_save, sender=Video)
def detect_original_change(sender, instance, **kwargs):
    """Flag initial uploads and replacements for asynchronous processing."""
    del sender, kwargs
    if instance.pk is None:
        instance.enqueue_processing = bool(instance.original)
        return
    previous_name = (
        Video.objects.filter(pk=instance.pk).values_list('original', flat=True).first()
    )
    instance.enqueue_processing = bool(instance.original) and (
        instance.original.name != previous_name
    )
    if instance.enqueue_processing:
        instance.processing_status = Video.ProcessingStatus.PENDING
        instance.processing_error = ''


@receiver(post_save, sender=Video)
def enqueue_changed_original(sender, instance, **kwargs):
    """Enqueue only after the upload record is safely committed."""
    del sender, kwargs
    if getattr(instance, 'enqueue_processing', False):
        transaction.on_commit(lambda: enqueue_video_processing(instance.pk))
