# -*- coding: utf-8 -*-
"""
First-run bootstrapper: download/prepare everything DepoSync needs so the user
never has to run a manual install again.

Steps (each reports progress via a callback):
  1. Create the install folder layout.
  2. Download & unpack FFmpeg (Windows) into <install>/tools.
  3. Pre-download the chosen Whisper model into <install>/models.
  4. Write the bundled legal/medical dictionaries into <install>/dict.
"""
import os
import sys
import zipfile
import shutil
import tempfile
import urllib.request
from typing import Callable

from deposync.config import CONFIG

FFMPEG_WIN_URL = ('https://www.gyan.dev/ffmpeg/builds/'
                  'ffmpeg-release-essentials.zip')

Progress = Callable[[int, str], None]


def _noop(p, m):
    pass


def ensure_layout(cb: Progress = _noop) -> None:
    cb(2, 'Creating folders...')
    for name in ('tools', 'models', 'dict', 'jobs', 'exhibits',
                 'exports', 'logs'):
        CONFIG.sub(name)


def ffmpeg_present() -> bool:
    return os.path.isfile(CONFIG.resolve_ffmpeg()) or \
        shutil.which('ffmpeg') is not None


def download_ffmpeg(cb: Progress = _noop) -> str:
    """Download + extract ffmpeg(.exe). Returns the resolved ffmpeg path."""
    exe = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
    dest = CONFIG.tools_dir / exe
    if dest.is_file():
        cb(100, 'FFmpeg already installed.')
        return str(dest)
    if sys.platform != 'win32':
        found = shutil.which('ffmpeg')
        if found:
            cb(100, f'Using system FFmpeg: {found}')
            return found
        raise RuntimeError('Install ffmpeg via your package manager.')

    cb(5, 'Downloading FFmpeg...')
    tmp_zip = os.path.join(tempfile.gettempdir(), 'ffmpeg_dl.zip')

    def _hook(blocks, bs, total):
        if total > 0:
            cb(min(70, int(blocks * bs / total * 65) + 5), 'Downloading FFmpeg...')

    urllib.request.urlretrieve(FFMPEG_WIN_URL, tmp_zip, _hook)
    cb(75, 'Extracting FFmpeg...')
    with zipfile.ZipFile(tmp_zip) as zf:
        member = next((n for n in zf.namelist()
                       if n.replace('\\', '/').endswith('bin/ffmpeg.exe')), None)
        if not member:
            raise RuntimeError('ffmpeg.exe not found in archive.')
        with zf.open(member) as src, open(dest, 'wb') as out:
            shutil.copyfileobj(src, out)
        probe = next((n for n in zf.namelist()
                      if n.replace('\\', '/').endswith('bin/ffprobe.exe')), None)
        if probe:
            with zf.open(probe) as src, open(CONFIG.tools_dir / 'ffprobe.exe',
                                             'wb') as out:
                shutil.copyfileobj(src, out)
    try:
        os.remove(tmp_zip)
    except OSError:
        pass
    CONFIG.set('ffmpeg_path', str(dest))
    cb(100, 'FFmpeg ready.')
    return str(dest)


def download_model(model_size: str, cb: Progress = _noop) -> None:
    """Pre-fetch a faster-whisper model into <install>/models."""
    cb(10, f'Downloading Whisper model "{model_size}"...')
    os.environ.setdefault('HF_HOME', str(CONFIG.models_dir))
    try:
        from faster_whisper import download_model as fw_download
        fw_download(model_size, output_dir=str(CONFIG.models_dir / model_size))
        cb(100, f'Model "{model_size}" ready.')
    except Exception as e:
        cb(100, f'Model will download on first sync ({e}).')


def write_dictionaries(cb: Progress = _noop) -> None:
    """Persist the bundled legal/medical base lists to <install>/dict."""
    cb(20, 'Installing legal & medical dictionaries...')
    from deposync.setup.dictionaries import _BASE_LEGAL, _BASE_MEDICAL
    (CONFIG.dict_dir / 'legal_base.txt').write_text(
        '\n'.join(sorted(set(_BASE_LEGAL))), 'utf-8')
    (CONFIG.dict_dir / 'medical_base.txt').write_text(
        '\n'.join(sorted(set(_BASE_MEDICAL))), 'utf-8')
    cb(100, 'Dictionaries installed.')


def run_full_setup(install_dir: str, model_size: str = 'base.en',
                   cb: Progress = _noop) -> None:
    """Top-level setup used by the first-run wizard."""
    CONFIG.set_install_dir(install_dir)
    cb(0, 'Starting setup...')
    ensure_layout(cb)
    cb(10, 'FFmpeg...')
    try:
        download_ffmpeg(cb)
    except Exception as e:
        cb(40, f'FFmpeg step skipped: {e}')
    write_dictionaries(cb)
    download_model(model_size, cb)
    CONFIG.set('model', model_size)
    CONFIG.set('setup_complete', True)
    cb(100, 'Setup complete.')


def create_desktop_shortcut(target_exe: str, name: str = 'DepoSync') -> str:
    """Create a Windows desktop shortcut to the app. Returns the .lnk path."""
    if sys.platform != 'win32':
        return ''
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    lnk = os.path.join(desktop, f'{name}.lnk')
    ps = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{target_exe}';"
        f"$s.WorkingDirectory='{os.path.dirname(target_exe)}';"
        f"$s.Save()")
    import subprocess
    subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                   capture_output=True)
    return lnk
