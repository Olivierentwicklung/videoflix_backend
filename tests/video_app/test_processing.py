"""Tests for asynchronous video upload processing."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from video_app.models import Category, Video
from video_app.tasks import process_video

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def temporary_media_root(settings, tmp_path):
    """Use a temporary media root whose path contains spaces."""
    settings.MEDIA_ROOT = tmp_path / 'media root with spaces'
    settings.FFMPEG_BINARY = 'ffmpeg'
    settings.FFPROBE_BINARY = 'ffprobe'


@pytest.fixture
def category():
    """Create the category required by video fixtures."""
    return Category.objects.create(name=Category.CategoryChoices.DRAMA)


def original_file(name='movie with spaces.mp4'):
    """Return a small in-memory source-video upload."""
    return SimpleUploadedFile(name, b'video-content', content_type='video/mp4')


def create_video(category, **overrides):
    """Create a video with valid processing defaults."""
    values = {
        'title': 'Movie',
        'description': 'Description',
        'category': category,
        'original': original_file(),
    }
    values.update(overrides)
    return Video.objects.create(**values)


def test_original_uses_unique_video_directory(category):
    """Store every source and generated artifact under its UUID directory."""
    video = create_video(category)

    assert video.original.name == f'videos/{video.storage_id}/original.mp4'
    assert video.output_directory == Path(video.original.path).parent
    assert video.thumbnail_output_path == video.output_directory / 'thumbnail.jpg'
    assert video.master_playlist_path == video.output_directory / 'master.m3u8'
    assert video.variant_playlist_path('720p') == (
        video.output_directory / '720p' / 'index.m3u8'
    )


def test_upload_enqueues_processing_after_commit(
    category, mocker, django_capture_on_commit_callbacks
):
    """Enqueue a newly stored original only after its transaction commits."""
    queue = mocker.Mock()
    mocker.patch('video_app.signals.get_queue', return_value=queue)

    with django_capture_on_commit_callbacks(execute=True):
        video = create_video(category)

    queue.enqueue.assert_called_once_with(process_video, video.pk)


def test_metadata_change_does_not_enqueue(category, mocker):
    """Avoid expensive reprocessing for metadata-only changes."""
    video = create_video(category)
    queue = mocker.Mock()
    mocker.patch('video_app.signals.get_queue', return_value=queue)

    video.title = 'Changed title'
    video.save()

    queue.enqueue.assert_not_called()


def test_replacing_original_enqueues_again(
    category, mocker, django_capture_on_commit_callbacks
):
    """Reset and enqueue processing when an original is replaced."""
    video = create_video(category)
    queue = mocker.Mock()
    mocker.patch('video_app.signals.get_queue', return_value=queue)

    with django_capture_on_commit_callbacks(execute=True):
        video.original = original_file('replacement.mov')
        video.save()

    queue.enqueue.assert_called_once_with(process_video, video.pk)
    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.PENDING


def test_queue_failure_is_recorded(
    category, mocker, django_capture_on_commit_callbacks
):
    """Record queue infrastructure failures on the video."""
    queue = mocker.Mock()
    queue.enqueue.side_effect = RuntimeError('redis unavailable')
    mocker.patch('video_app.signals.get_queue', return_value=queue)

    with django_capture_on_commit_callbacks(execute=True):
        video = create_video(category)
    video.refresh_from_db()

    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'redis unavailable' in video.processing_error


def expected_outputs(video):
    """Create the output files expected from a mocked successful FFmpeg run."""
    video.thumbnail_output_path.parent.mkdir(parents=True, exist_ok=True)
    video.thumbnail_output_path.write_bytes(b'jpeg')
    video.master_playlist_path.write_text('#EXTM3U\n', encoding='utf-8')
    for resolution in ('480p', '720p', '1080p'):
        playlist = video.variant_playlist_path(resolution)
        playlist.parent.mkdir(parents=True, exist_ok=True)
        playlist.write_text('#EXTM3U\n', encoding='utf-8')
        (playlist.parent / 'segment_000.ts').write_bytes(b'segment')


def test_processing_builds_expected_ffmpeg_commands_and_marks_ready(
    category, mocker
):
    """Build the adaptive HLS commands and publish successful output."""
    video = create_video(category)

    def run(command, **kwargs):
        """Emulate FFprobe and FFmpeg while materializing expected outputs."""
        assert isinstance(command, list)
        assert kwargs == {'capture_output': True, 'text': True, 'check': False}
        if command[0] == 'ffprobe':
            return CompletedProcess(command, 0, '1\n', '')
        if '-hls_time' in command:
            expected_outputs(video)
        return CompletedProcess(command, 0, '', '')

    run_mock = mocker.patch('video_app.tasks.subprocess.run', side_effect=run)

    process_video(video.pk)

    probe_command, thumbnail_command, hls_command = [
        call.args[0] for call in run_mock.call_args_list
    ]
    assert probe_command[0] == 'ffprobe'
    assert probe_command[-1] == video.original.path
    assert thumbnail_command[thumbnail_command.index('-i') + 1] == video.original.path
    assert thumbnail_command[-1] == str(video.thumbnail_output_path)
    assert 'scale=-2:480' in hls_command[hls_command.index('-filter_complex') + 1]
    assert 'scale=-2:720' in hls_command[hls_command.index('-filter_complex') + 1]
    assert 'scale=-2:1080' in hls_command[hls_command.index('-filter_complex') + 1]
    assert hls_command[hls_command.index('-hls_time') + 1] == '6'
    assert hls_command[hls_command.index('-hls_playlist_type') + 1] == 'vod'
    assert hls_command[hls_command.index('-hls_flags') + 1] == 'independent_segments'
    assert hls_command[hls_command.index('-master_pl_name') + 1] == 'master.m3u8'
    assert hls_command[-1].endswith('%v\\index.m3u8') or hls_command[-1].endswith(
        '%v/index.m3u8'
    )
    assert 'expr:gte(t,n_forced*6)' in hls_command
    assert 'libx264' in hls_command
    assert 'aac' in hls_command

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.READY
    assert video.processing_error == ''
    assert video.thumbnail.name == f'videos/{video.storage_id}/thumbnail.jpg'


def test_processing_adds_silent_aac_when_source_has_no_audio(category, mocker):
    """Supply silent AAC when FFprobe finds no source audio stream."""
    video = create_video(category)

    def run(command, **kwargs):
        """Emulate an audio-less probe followed by successful FFmpeg calls."""
        del kwargs
        if command[0] == 'ffprobe':
            return CompletedProcess(command, 0, '', '')
        if '-hls_time' in command:
            expected_outputs(video)
        return CompletedProcess(command, 0, '', '')

    run_mock = mocker.patch('video_app.tasks.subprocess.run', side_effect=run)

    process_video(video.pk)

    hls_command = run_mock.call_args_list[-1].args[0]
    assert 'anullsrc=channel_layout=stereo:sample_rate=48000' in hls_command
    assert hls_command.count('1:a:0') == 3
    assert '-shortest' in hls_command
    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.READY


def test_ffmpeg_failure_is_recorded(category, mocker):
    """Persist useful stderr when FFmpeg returns a failure code."""
    video = create_video(category)
    run_mock = mocker.patch('video_app.tasks.subprocess.run')
    run_mock.side_effect = [
        CompletedProcess([], 0, '1\n', ''),
        CompletedProcess([], 1, '', 'encoder exploded'),
    ]

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'encoder exploded' in video.processing_error


def test_missing_ffmpeg_is_recorded(category, mocker):
    """Record a missing FFmpeg executable as a processing failure."""
    video = create_video(category)
    run_mock = mocker.patch('video_app.tasks.subprocess.run')
    run_mock.side_effect = [
        CompletedProcess([], 0, '1\n', ''),
        FileNotFoundError(),
    ]

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'FFmpeg executable was not found' in video.processing_error


def test_missing_ffprobe_is_recorded(category, mocker):
    """Record a missing FFprobe executable as a processing failure."""
    video = create_video(category)
    mocker.patch('video_app.tasks.subprocess.run', side_effect=FileNotFoundError())

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'FFprobe executable was not found' in video.processing_error


def test_ffprobe_failure_is_recorded(category, mocker):
    """Persist FFprobe diagnostics when source inspection fails."""
    video = create_video(category)
    mocker.patch(
        'video_app.tasks.subprocess.run',
        return_value=CompletedProcess([], 1, '', 'probe failed'),
    )

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'probe failed' in video.processing_error


def test_processing_missing_database_record_is_a_noop():
    """Allow stale queued jobs for deleted videos to exit safely."""
    assert process_video(999) is None


def test_processing_record_without_original_is_failed(category):
    """Mark legacy records without an original as failed."""
    video = Video.objects.create(
        title='Legacy movie',
        description='Description',
        category=category,
    )

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert video.processing_error == 'The original video file is missing.'


def test_missing_expected_output_is_recorded(category, mocker):
    """Reject successful process exits that did not create required files."""
    video = create_video(category)
    run_mock = mocker.patch('video_app.tasks.subprocess.run')
    run_mock.side_effect = [
        CompletedProcess([], 0, '1\n', ''),
        CompletedProcess([], 0, '', ''),
        CompletedProcess([], 0, '', ''),
    ]

    process_video(video.pk)

    video.refresh_from_db()
    assert video.processing_status == Video.ProcessingStatus.FAILED
    assert 'expected output' in video.processing_error.lower()
