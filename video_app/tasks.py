"""Background jobs for generating streamable video media."""

import subprocess

from django.conf import settings

from video_app.models import Video

RESOLUTIONS = ('480p', '720p', '1080p')
ERROR_LIMIT = 4000


class VideoProcessingError(RuntimeError):
    """Represent an expected processing failure suitable for admin display."""


def _run_ffmpeg(command):
    """Run one FFmpeg command and raise with its diagnostic on failure."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VideoProcessingError('FFmpeg executable was not found.') from exc

    if result.returncode:
        diagnostic = (result.stderr or result.stdout or 'Unknown FFmpeg error').strip()
        raise VideoProcessingError(diagnostic[-ERROR_LIMIT:])


def _source_has_audio(video):
    """Use FFprobe to determine whether the source contains an audio stream."""
    command = [
        settings.FFPROBE_BINARY,
        '-v',
        'error',
        '-select_streams',
        'a:0',
        '-show_entries',
        'stream=index',
        '-of',
        'csv=p=0',
        video.original.path,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VideoProcessingError('FFprobe executable was not found.') from exc
    if result.returncode:
        diagnostic = (result.stderr or result.stdout or 'Unknown FFprobe error').strip()
        raise VideoProcessingError(diagnostic[-ERROR_LIMIT:])
    return bool(result.stdout.strip())


def _thumbnail_command(video):
    """Build the safe thumbnail extraction command."""
    return [
        settings.FFMPEG_BINARY,
        '-y',
        '-ss',
        '1',
        '-i',
        video.original.path,
        '-frames:v',
        '1',
        '-q:v',
        '2',
        str(video.thumbnail_output_path),
    ]


def _hls_command(video, source_has_audio):
    """Build one aligned adaptive HLS transcode command."""
    output_directory = video.output_directory
    filter_graph = (
        '[0:v]split=3[v480src][v720src][v1080src];'
        '[v480src]scale=-2:480,setsar=1[v480];'
        '[v720src]scale=-2:720,setsar=1[v720];'
        '[v1080src]scale=-2:1080,setsar=1[v1080]'
    )
    command = [
        settings.FFMPEG_BINARY,
        '-y',
        '-i',
        video.original.path,
    ]
    if not source_has_audio:
        command.extend(
            [
                '-f',
                'lavfi',
                '-i',
                'anullsrc=channel_layout=stereo:sample_rate=48000',
            ]
        )
    command.extend(
        [
        '-filter_complex',
        filter_graph,
        ]
    )
    audio_stream = '0:a:0' if source_has_audio else '1:a:0'
    for video_stream, audio_stream in (
        ('[v480]', audio_stream),
        ('[v720]', audio_stream),
        ('[v1080]', audio_stream),
    ):
        command.extend(['-map', video_stream, '-map', audio_stream])

    command.extend(
        [
            '-c:v',
            'libx264',
            '-preset',
            'medium',
            '-profile:v',
            'main',
            '-pix_fmt',
            'yuv420p',
            '-b:v:0',
            '1400k',
            '-maxrate:v:0',
            '1498k',
            '-bufsize:v:0',
            '2100k',
            '-b:v:1',
            '2800k',
            '-maxrate:v:1',
            '2996k',
            '-bufsize:v:1',
            '4200k',
            '-b:v:2',
            '5000k',
            '-maxrate:v:2',
            '5350k',
            '-bufsize:v:2',
            '7500k',
            '-c:a',
            'aac',
            '-b:a:0',
            '128k',
            '-b:a:1',
            '128k',
            '-b:a:2',
            '192k',
            '-ac',
            '2',
            '-ar',
            '48000',
            '-sc_threshold',
            '0',
        ]
    )
    for stream_index in range(3):
        command.extend(
            [
                f'-force_key_frames:v:{stream_index}',
                'expr:gte(t,n_forced*6)',
            ]
        )
    if not source_has_audio:
        command.append('-shortest')
    command.extend(
        [
            '-f',
            'hls',
            '-hls_time',
            '6',
            '-hls_playlist_type',
            'vod',
            '-hls_flags',
            'independent_segments',
            '-hls_segment_filename',
            str(output_directory / '%v' / 'segment_%03d.ts'),
            '-master_pl_name',
            'master.m3u8',
            '-var_stream_map',
            'v:0,a:0,name:480p v:1,a:1,name:720p v:2,a:2,name:1080p',
            str(output_directory / '%v' / 'index.m3u8'),
        ]
    )
    return command


def _validate_outputs(video):
    """Ensure FFmpeg produced every public artifact before publishing ready."""
    expected = [video.thumbnail_output_path, video.master_playlist_path]
    expected.extend(video.variant_playlist_path(value) for value in RESOLUTIONS)
    missing = [str(path) for path in expected if not path.is_file()]
    for resolution in RESOLUTIONS:
        if not any((video.output_directory / resolution).glob('segment_*.ts')):
            missing.append(str(video.output_directory / resolution / 'segment_*.ts'))
    if missing:
        raise VideoProcessingError(
            f'FFmpeg did not create expected output: {", ".join(missing)}'
        )


def _set_failed(video_id, error):
    """Persist a bounded failure diagnostic without firing model signals."""
    Video.objects.filter(pk=video_id).update(
        processing_status=Video.ProcessingStatus.FAILED,
        processing_error=str(error)[-ERROR_LIMIT:],
    )


def process_video(video_id):
    """Generate a thumbnail and three adaptive HLS variants for one video."""
    try:
        video = Video.objects.get(pk=video_id)
    except Video.DoesNotExist:
        return

    Video.objects.filter(pk=video_id).update(
        processing_status=Video.ProcessingStatus.PROCESSING,
        processing_error='',
    )

    try:
        if not video.original:
            raise VideoProcessingError('The original video file is missing.')
        video.output_directory.mkdir(parents=True, exist_ok=True)
        for resolution in RESOLUTIONS:
            (video.output_directory / resolution).mkdir(parents=True, exist_ok=True)
        source_has_audio = _source_has_audio(video)
        _run_ffmpeg(_thumbnail_command(video))
        _run_ffmpeg(_hls_command(video, source_has_audio))
        _validate_outputs(video)
    except (OSError, VideoProcessingError) as exc:
        _set_failed(video_id, exc)
        return

    thumbnail_name = f'videos/{video.storage_id}/thumbnail.jpg'
    Video.objects.filter(pk=video_id).update(
        thumbnail=thumbnail_name,
        processing_status=Video.ProcessingStatus.READY,
        processing_error='',
    )
