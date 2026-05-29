# -*- coding: utf-8 -*-
"""
Central configuration + path management for DepoSync.

A tiny bootstrap config lives in the OS app-data folder and points at the
user-chosen INSTALL directory (set during first-run setup). The install
directory holds everything the app needs so nothing re-downloads each launch:

    <install>/tools     FFmpeg (ffmpeg.exe) and other binaries
    <install>/models    Whisper / faster-whisper model files
    <install>/dict      Legal & medical dictionaries
    <install>/jobs      Job library (jobs.db + per-job assets)
    <install>/exhibits  Imported exhibit files (copied per job)
    <install>/exports   Saved export files
    <install>/logs      Logs
"""
import os
import sys
import json
from pathlib import Path

APP_NAME = 'DepoSync'


def appdata_dir() -> Path:
    """OS-appropriate per-user config dir (holds only the bootstrap pointer)."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


BOOTSTRAP_CONFIG = appdata_dir() / 'config.json'

DEFAULT_SETTINGS = {
    'install_dir': '',         # set during first-run setup
    'setup_complete': False,
    'model': 'base.en',        # per-job default; overridable in Settings/wizard
    'language': 'en',
    'playback_speed': 1.0,
    'use_gpu': True,           # auto-detect; this just allows disabling
    'ffmpeg_path': '',         # explicit ffmpeg.exe path if bundled
}


class Config:
    def __init__(self):
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if BOOTSTRAP_CONFIG.exists():
            try:
                self.data.update(json.loads(BOOTSTRAP_CONFIG.read_text('utf-8')))
            except Exception:
                pass

    def save(self):
        try:
            BOOTSTRAP_CONFIG.write_text(json.dumps(self.data, indent=2), 'utf-8')
        except Exception:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # ---- paths ----------------------------------------------------------
    @property
    def install_dir(self) -> Path:
        d = self.data.get('install_dir')
        return Path(d) if d else appdata_dir()

    def set_install_dir(self, path):
        self.data['install_dir'] = str(path)
        self.save()

    def sub(self, name) -> Path:
        p = self.install_dir / name
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    @property
    def tools_dir(self) -> Path:   return self.sub('tools')

    @property
    def models_dir(self) -> Path:  return self.sub('models')

    @property
    def dict_dir(self) -> Path:    return self.sub('dict')

    @property
    def jobs_dir(self) -> Path:    return self.sub('jobs')

    @property
    def exhibits_dir(self) -> Path: return self.sub('exhibits')

    @property
    def exports_dir(self) -> Path: return self.sub('exports')

    @property
    def logs_dir(self) -> Path:    return self.sub('logs')

    def resolve_ffmpeg(self) -> str:
        """Return a usable ffmpeg command/path (bundled > config > PATH)."""
        import shutil
        explicit = self.data.get('ffmpeg_path')
        if explicit and os.path.isfile(explicit):
            return explicit
        exe = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        bundled = self.tools_dir / exe
        if bundled.is_file():
            return str(bundled)
        found = shutil.which('ffmpeg')
        return found or 'ffmpeg'


# Singleton used across the app.
CONFIG = Config()
