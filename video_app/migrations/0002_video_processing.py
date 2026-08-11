import uuid

from django.db import migrations, models

import video_app.models


def populate_storage_ids(apps, schema_editor):
    del schema_editor
    video_model = apps.get_model('video_app', 'Video')
    for video in video_model.objects.filter(storage_id__isnull=True).iterator():
        video.storage_id = uuid.uuid4()
        video.save(update_fields=['storage_id'])


class Migration(migrations.Migration):

    dependencies = [('video_app', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='video',
            name='storage_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_storage_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='video',
            name='storage_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='video',
            name='original',
            field=models.FileField(
                blank=True,
                upload_to=video_app.models.original_video_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name='video',
            name='thumbnail',
            field=models.ImageField(blank=True, editable=False, upload_to='thumbnails/'),
        ),
        migrations.AddField(
            model_name='video',
            name='processing_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('ready', 'Ready'),
                    ('failed', 'Failed'),
                ],
                default='ready',
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='video',
            name='processing_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('ready', 'Ready'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='video',
            name='processing_error',
            field=models.TextField(blank=True, default='', editable=False),
        ),
    ]
