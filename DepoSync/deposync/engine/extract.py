import os
import subprocess
import tempfile

from deposync import debuglog as _dbg


def wav_path_for(video_path: str) -> str:
    """The companion WAV that lives next to the video: <base>_synclync.wav."""
    d = os.path.dirname(os.path.abspath(video_path))
    base = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(d, f'{base}_synclync.wav')


def to_wav(video_path: str, start_sec: float = 0.0,
           duration_sec: float = None, reuse: bool = True) -> str:
    """
    Extract a 16 kHz mono PCM WAV from a video using ffmpeg, writing it
    NEXT TO the video as <base>_synclync.wav. If that file already exists it
    is reused (instant), so a re-sync of the same video is immediate.

    Timecodes always refer to the video timeline (the WAV is a faithful copy
    of the video's audio starting at the same t=0).
    """
    companion = wav_path_for(video_path)

    if reuse and start_sec == 0 and not duration_sec:
        try:
            if os.path.isfile(companion) and os.path.getsize(companion) > 1024:
                _dbg.log(f'extract: reusing existing WAV {companion} '
                         f'({os.path.getsize(companion)} bytes)')
                return companion
        except Exception:
            pass

    # Decide output target: next to video if writable, else temp.
    out = companion
    try:
        d = os.path.dirname(companion)
        if not os.access(d, os.W_OK):
            out = tempfile.mktemp(suffix='_synclync.wav')
            _dbg.log(f'extract: video folder not writable, using temp {out}')
    except Exception:
        out = tempfile.mktemp(suffix='_synclync.wav')

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

    _dbg.log(f'extract: running ffmpeg -> {out}')
    _dbg.log(f'extract: cmd = {" ".join(cmd)}')
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode('utf-8', 'replace')[:400]
        _dbg.log(f'extract: FFMPEG FAILED rc={r.returncode}: {err}')
        raise RuntimeError(f'FFmpeg failed:\n{err}')
    if not os.path.exists(out) or os.path.getsize(out) < 1024:
        _dbg.log('extract: ffmpeg produced no usable output')
        raise RuntimeError('FFmpeg produced no usable audio output.')
    _dbg.log(f'extract: done, {os.path.getsize(out)} bytes at {out}')
    return out
