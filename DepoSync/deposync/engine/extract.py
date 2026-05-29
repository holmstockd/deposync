import os
import subprocess
import tempfile


def to_wav(video_path: str, start_sec: float = 0.0,
           duration_sec: float = None) -> str:
    """
    Extract a 16 kHz mono PCM WAV from a video/audio file using ffmpeg.

    Writes to a real temp file (never a pipe) so the WAV trailer can be
    written correctly, and drops the video stream (-vn) for speed.
    """
    out = tempfile.mktemp(suffix='.wav')

    try:
        from deposync.config import CONFIG
        ffmpeg = CONFIG.resolve_ffmpeg()
    except Exception:
        ffmpeg = 'ffmpeg'

    cmd = [ffmpeg, '-y', '-nostdin', '-loglevel', 'error']
    if start_sec and start_sec > 0:
        cmd += ['-ss', str(start_sec)]
    cmd += ['-i', video_path]
    if duration_sec and duration_sec > 0:
        cmd += ['-t', str(duration_sec)]
    cmd += ['-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
            '-f', 'wav', out]

    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f'FFmpeg failed:\n{r.stderr.decode("utf-8", "replace")[:400]}')
    if not os.path.exists(out) or os.path.getsize(out) < 1024:
        raise RuntimeError('FFmpeg produced no usable audio output.')
    return out
