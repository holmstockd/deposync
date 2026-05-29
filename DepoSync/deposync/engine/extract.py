import os, subprocess, tempfile

def to_wav(video_path: str, start_sec: float = 0.0,
           duration_sec: float = None) -> str:
    out = tempfile.mktemp(suffix='.wav')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error']
    if start_sec > 0:
        cmd += ['-ss', str(start_sec)]
    cmd += ['-i', video_path]
    if duration_sec and duration_sec > 0:
        cmd += ['-t', str(duration_sec)]
    cmd += ['-ac', '1', '-ar', '16000', '-f', 'wav', out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f'FFmpeg failed:\n{r.stderr.decode("utf-8","replace")[:400]}')
    if not os.path.exists(out):
        raise RuntimeError('FFmpeg produced no output.')
    return out
