# -*- coding: utf-8 -*-
"""
Embedded VLC player widget for PyQt6.
Emits position_changed(float) and duration_changed(float) signals.
"""
import sys
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt6.QtGui     import QPalette, QColor


class VLCPlayerWidget(QWidget):
    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._instance     = None
        self._player       = None
        self._dur          = 0.0
        self._poll_timer   = QTimer(self)
        self._poll_timer.setInterval(250)
        self._poll_timer.timeout.connect(self._poll)

        self._frame = QFrame(self)
        self._frame.setMinimumHeight(240)
        pal = self._frame.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self._frame.setPalette(pal)
        self._frame.setAutoFillBackground(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._frame)

        try:
            import vlc
            self._instance = vlc.Instance('--no-xlib --quiet')
            self._player   = self._instance.media_player_new()
            if sys.platform == 'win32':
                self._player.set_hwnd(int(self._frame.winId()))
            elif sys.platform == 'darwin':
                self._player.set_nsobject(int(self._frame.winId()))
            else:
                self._player.set_xwindow(int(self._frame.winId()))
        except Exception as e:
            print(f'VLC init failed: {e}')

    def load(self, path: str, autoplay: bool = False):
        if not self._player:
            return
        try:
            media = self._instance.media_new(path)
            try:
                media.parse_with_options(1, 0)   # MediaParseFlag.local -> get duration
            except Exception:
                pass
            self._player.set_media(media)
            if autoplay:
                self._player.play()
            self._poll_timer.start()
            QTimer.singleShot(500, self._get_duration)
        except Exception as e:
            print(f'VLC load failed: {e}')

    def _get_duration(self):
        if not self._player:
            return
        try:
            d = self._player.get_length() / 1000.0
            if d > 0:
                self._dur = d
                self.duration_changed.emit(d)
            else:
                QTimer.singleShot(500, self._get_duration)
        except Exception:
            pass

    def _poll(self):
        if not self._player:
            return
        try:
            pos = self._player.get_time() / 1000.0
            if pos >= 0:
                self.position_changed.emit(pos)
        except Exception:
            pass

    def play(self):
        if self._player:
            try: self._player.set_pause(0); self._player.play(); self._poll_timer.start()
            except Exception: pass

    def pause(self):
        if self._player:
            try: self._player.set_pause(1)
            except Exception: pass

    def stop(self):
        """Hard stop: halts video AND audio (used during sync)."""
        if self._player:
            try:
                self._player.stop()
                self._poll_timer.stop()
            except Exception: pass

    def set_mute(self, on: bool):
        if self._player:
            try: self._player.audio_set_mute(bool(on))
            except Exception: pass

    def seek(self, t: float):
        if self._player:
            try: self._player.set_time(int(max(0.0, t) * 1000))
            except Exception: pass

    def get_position(self) -> float:
        if not self._player:
            return 0.0
        try: return max(0.0, self._player.get_time() / 1000.0)
        except Exception: return 0.0

    def get_duration(self) -> float:
        return self._dur

    def is_playing(self) -> bool:
        if not self._player:
            return False
        try: return self._player.is_playing() == 1
        except Exception: return False

    def set_rate(self, rate: float):
        if self._player:
            try: self._player.set_rate(rate)
            except Exception: pass
