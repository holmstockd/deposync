# -*- coding: utf-8 -*-
"""
DepoSync -- Legal Deposition Video Sync

EXACT FLOW:
  1. User clicks "Add Transcript"
     -> File dialog opens
     -> Transcript loads, table fills
     -> IMMEDIATELY: Setup Wizard opens (transcript + videos + sync?)

  SETUP WIZARD (single dialog, sequential pages):
     Page A: Shows transcript info, asks how many videos
     Page B: For each video -- Browse file + Start page:line + End page:line
             (one page per video, auto-filled from transcript scan)
     Page C: Summary + "Sync Now?" Yes / No

  If YES  -> progress dialog with accurate step-by-step bars
  If NO   -> main window, "Sync Now" button visible, sync when ready

  After sync: Results dialog -> Review table -> Export
"""
import sys, os, time, traceback as _tb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

# ?? crash log ?????????????????????????????????????????????????????????????????
_LOG = os.path.join(os.path.expanduser('~'), 'DepoSync_crash.log')

def _write_crash(msg=''):
    try:
        import datetime
        with open(_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH {datetime.datetime.now()}\n")
            if msg: f.write(msg + '\n')
    except Exception:
        pass

def _write_ok():
    try:
        import datetime
        with open(_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Started OK {datetime.datetime.now()}\n")
    except Exception:
        pass

# ?? imports ???????????????????????????????????????????????????????????????????
from PyQt6.QtCore    import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui     import QColor, QFont, QBrush, QPalette, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog, QProgressBar, QStatusBar,
    QMessageBox, QToolBar, QSplitter, QSlider, QDialog,
    QDialogButtonBox, QComboBox, QSpinBox, QGroupBox, QFormLayout,
    QLineEdit, QFrame, QStackedWidget, QScrollArea,
)

C_GN_BG=QColor(10,35,10);  C_GN_FG=QColor(70,190,70)
C_AM_BG=QColor(35,25, 4);  C_AM_FG=QColor(210,150,35)
C_RD_BG=QColor(44, 8, 8);  C_RD_FG=QColor(210, 50,50)
C_NO_BG=QColor(20,12,12);  C_NO_FG=QColor(88, 52,52)
C_MN_BG=QColor(10,28,50);  C_MN_FG=QColor(100,180,255)
CONF_GREEN=0.97; CONF_AMBER=0.70

def _mono():
    f=QFont('Consolas',9); f.setStyleHint(QFont.StyleHint.Monospace); return f

def _hms(t):
    if t is None: return ''
    return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{t%60:06.3f}"


# =============================================================================
# SETUP WIZARD
# =============================================================================

class SetupWizard(QDialog):
    """
    Single dialog that walks through the complete job setup:
      Step 1 : How many videos?
      Step 2+: One page per video -- file + start page:line + end page:line
      Final  : Confirm + Sync Now? Yes / No
    """
    def __init__(self, transcript_path, lines, auto_sp, auto_sl, auto_ep, auto_el, parent=None):
        super().__init__(parent)
        self.setWindowTitle('DepoSync -- Job Setup')
        self.setMinimumWidth(600)
        self.setMinimumHeight(420)

        self._lines       = lines
        self._t_path      = transcript_path
        self._auto_sp     = auto_sp
        self._auto_sl     = auto_sl
        self._auto_ep     = auto_ep
        self._auto_el     = auto_el
        self._last_page   = lines[-1].page
        self._n_videos    = 1
        self._video_data  = []   # [{path, sp, sl, ep, el}, ...]
        self._sync_now    = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,12,16,12)
        lay.setSpacing(8)

        # Title
        self._title = QLabel('')
        self._title.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        self._title.setStyleSheet('color:#5bc8ff; padding:4px 0;')
        lay.addWidget(self._title)

        # Transcript info bar
        fp = lines[0].page; lp = lines[-1].page
        t_info = QLabel(
            f'<b>{os.path.basename(transcript_path)}</b>   '
            f'{len(lines)} lines   pages {fp}?{lp}   '
            f'<span style="color:#5bc8ff;">'
            f'Testimony: p{auto_sp}:{auto_sl} ? p{auto_ep}:{auto_el}'
            f'</span>')
        t_info.setStyleSheet('color:#aaa; font-size:10px; padding:2px 0 6px 0;')
        t_info.setWordWrap(True)
        lay.addWidget(t_info)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color:#333;')
        lay.addWidget(sep)

        # Stacked pages
        self._stack = QStackedWidget()
        lay.addWidget(self._stack, 1)

        # Nav buttons
        nav = QHBoxLayout()
        self._btn_back = QPushButton('< Back')
        self._btn_back.setFixedWidth(90)
        self._btn_back.clicked.connect(self._back)
        self._btn_next = QPushButton('Next >')
        self._btn_next.setFixedWidth(90)
        self._btn_next.setDefault(True)
        self._btn_next.clicked.connect(self._next)
        self._btn_sync = QPushButton('Sync Now')
        self._btn_sync.setFixedWidth(120)
        self._btn_sync.setStyleSheet(
            'background:#007acc;color:#fff;font-weight:bold;padding:4px 10px;')
        self._btn_sync.clicked.connect(self._do_sync_now)
        self._btn_later = QPushButton('Later')
        self._btn_later.setFixedWidth(90)
        self._btn_later.clicked.connect(self._do_later)
        self._btn_cancel = QPushButton('Cancel')
        self._btn_cancel.setFixedWidth(90)
        self._btn_cancel.clicked.connect(self.reject)
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_cancel)
        nav.addStretch()
        nav.addWidget(self._btn_later)
        nav.addWidget(self._btn_sync)
        nav.addWidget(self._btn_next)
        lay.addLayout(nav)

        self._build_step1()
        self._show_page(0)

    # ?? Step 1: How many videos? ???????????????????????????????????????????????

    def _build_step1(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        l.addWidget(QLabel(
            'How many video or audio files cover this deposition?\n\n'
            '  ? Single recording  ?  1\n'
            '  ? AM + PM session   ?  2\n'
            '  ? Vol. 1, 2, 3 ?   ?  enter the count'))

        row = QHBoxLayout()
        row.addWidget(QLabel('Number of videos:'))
        self._n_spin = QSpinBox()
        self._n_spin.setRange(1, 20)
        self._n_spin.setValue(1)
        self._n_spin.setFixedWidth(80)
        row.addWidget(self._n_spin)
        row.addStretch()
        l.addLayout(row)
        l.addStretch()
        self._stack.addWidget(w)   # index 0

    # ?? Step 2+: Per-video file + page:line ???????????????????????????????????

    def _build_video_page(self, idx, total, sp, sl, ep, el):
        w   = QScrollArea()
        w.setWidgetResizable(True)
        inner = QWidget()
        l     = QVBoxLayout(inner)
        l.setSpacing(10)

        title = (f'Video {idx+1} of {total}'
                 if total > 1 else 'Video File')
        l.addWidget(QLabel(f'<b>{title}</b>'))

        # File
        file_grp = QGroupBox('Video / Audio File')
        fl = QHBoxLayout(file_grp)
        path_lbl = QLabel('? not selected ?')
        path_lbl.setStyleSheet('color:#888;font-size:10px;')
        browse = QPushButton('Browse...')
        browse.setFixedWidth(90)
        fl.addWidget(path_lbl, 1)
        fl.addWidget(browse)
        l.addWidget(file_grp)

        # Start page:line
        start_grp = QGroupBox('Start of Testimony in This Video')
        sg = QHBoxLayout(start_grp)
        sg.addWidget(QLabel('Page:'))
        sp_spin = QSpinBox(); sp_spin.setRange(1, self._last_page)
        sp_spin.setValue(sp); sp_spin.setFixedWidth(70)
        sl_spin = QSpinBox(); sl_spin.setRange(1, 25)
        sl_spin.setValue(sl); sl_spin.setFixedWidth(60)
        sg.addWidget(sp_spin); sg.addWidget(QLabel('  Line:'))
        sg.addWidget(sl_spin); sg.addStretch()
        # Preview
        start_preview = QLabel('')
        start_preview.setStyleSheet('color:#5bc8ff;font-size:10px;')
        start_preview.setWordWrap(True)
        sg.addWidget(start_preview, 1)
        l.addWidget(start_grp)

        # End page:line
        end_grp = QGroupBox('End of Testimony in This Video')
        eg = QHBoxLayout(end_grp)
        eg.addWidget(QLabel('Page:'))
        ep_spin = QSpinBox(); ep_spin.setRange(1, self._last_page)
        ep_spin.setValue(ep); ep_spin.setFixedWidth(70)
        el_spin = QSpinBox(); el_spin.setRange(1, 25)
        el_spin.setValue(el); el_spin.setFixedWidth(60)
        eg.addWidget(ep_spin); eg.addWidget(QLabel('  Line:'))
        eg.addWidget(el_spin); eg.addStretch()
        end_preview = QLabel('')
        end_preview.setStyleSheet('color:#ff8c00;font-size:10px;')
        end_preview.setWordWrap(True)
        eg.addWidget(end_preview, 1)
        l.addWidget(end_grp)

        l.addStretch()
        w.setWidget(inner)

        # Wire up previews
        lkp = {(ln.page, ln.line_num): ln.text for ln in self._lines}
        def _upd_preview(*_):
            s = lkp.get((sp_spin.value(), sl_spin.value()), '')
            e = lkp.get((ep_spin.value(), el_spin.value()), '')
            if not s:
                # nearest line on page
                s = next((ln.text for ln in self._lines
                          if ln.page == sp_spin.value()), '(not found)')
            if not e:
                e = next((ln.text for ln in reversed(self._lines)
                          if ln.page == ep_spin.value()), '(not found)')
            start_preview.setText(f'? "{s[:55]}"')
            end_preview.setText(  f'? "{e[:55]}"')
        sp_spin.valueChanged.connect(_upd_preview)
        sl_spin.valueChanged.connect(_upd_preview)
        ep_spin.valueChanged.connect(_upd_preview)
        el_spin.valueChanged.connect(_upd_preview)
        _upd_preview()

        # Store widget refs
        w._path_lbl  = path_lbl
        w._path      = ''
        w._sp        = sp_spin
        w._sl        = sl_spin
        w._ep        = ep_spin
        w._el        = el_spin

        def _browse():
            p, _ = QFileDialog.getOpenFileName(
                self, f'Select Video {idx+1}', '',
                'Media (*.mpg *.mp4 *.avi *.mov *.mts *.wmv '
                '*.mp3 *.wav *.m4a *.aac);;All Files (*)')
            if p:
                w._path = p
                path_lbl.setText(os.path.basename(p))
                path_lbl.setStyleSheet('color:#ddd;font-size:10px;')
                path_lbl.setToolTip(p)
        browse.clicked.connect(_browse)

        self._stack.addWidget(w)   # indices 1..n
        return w

    # ?? Final confirmation page ????????????????????????????????????????????????

    def _build_confirm_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(8)

        lines = []
        for i, d in enumerate(self._video_data, 1):
            if len(self._video_data) > 1:
                lines.append(
                    f'<b>Video {i}:</b>  {os.path.basename(d["path"])}  '
                    f'<span style="color:#5bc8ff;">'
                    f'p{d["sp"]}:{d["sl"]} ? p{d["ep"]}:{d["el"]}'
                    f'</span>')
            else:
                lines.append(
                    f'<b>Video:</b>  {os.path.basename(d["path"])}  '
                    f'<span style="color:#5bc8ff;">'
                    f'p{d["sp"]}:{d["sl"]} ? p{d["ep"]}:{d["el"]}'
                    f'</span>')
        summary = QLabel('<br>'.join(lines))
        summary.setWordWrap(True)
        summary.setStyleSheet('padding:8px; background:#1a1a1a; border-radius:4px;')
        l.addWidget(summary)

        l.addWidget(QLabel(
            '<span style="color:#ffb74d;font-size:11px;">'
            'Ready to sync.  Click <b>Sync Now</b> to start, '
            'or <b>Later</b> to return to the main window first.'
            '</span>'))
        l.addStretch()
        self._stack.addWidget(w)
        return w

    # ?? Navigation ????????????????????????????????????????????????????????????

    def _show_page(self, idx):
        self._stack.setCurrentIndex(idx)
        total = self._stack.count() - 1  # last is confirm
        is_first  = (idx == 0)
        is_last   = (idx == total)

        self._btn_back.setVisible(not is_first)
        self._btn_next.setVisible(not is_last)
        self._btn_sync.setVisible(is_last)
        self._btn_later.setVisible(is_last)
        self._btn_cancel.setVisible(not is_last)

        if idx == 0:
            self._title.setText('Step 1 of %d  ?  How Many Videos?' %
                                 (self._n_spin.value() + 1))
        elif is_last:
            self._title.setText('Ready to Sync')
        else:
            n = self._n_spin.value()
            self._title.setText(
                f'Step {idx+1} of {n+1}  ?  Video {idx}')

    def _back(self):
        idx = self._stack.currentIndex()
        if idx > 0:
            self._show_page(idx - 1)

    def _next(self):
        idx = self._stack.currentIndex()

        # Leaving step 1: build video pages
        if idx == 0:
            n = self._n_spin.value()
            self._n_videos = n
            # Remove old video pages (indices 1..count-2) and confirm (last)
            while self._stack.count() > 1:
                w = self._stack.widget(1)
                self._stack.removeWidget(w)
                w.deleteLater()

            # Calculate default page ranges per video
            total_pgs = self._auto_ep - self._auto_sp + 1
            chunk     = max(1, total_pgs // n)
            self._vpages = []
            for i in range(n):
                if n == 1:
                    sp, sl, ep, el = self._auto_sp, self._auto_sl, self._auto_ep, self._auto_el
                elif i == 0:
                    sp, sl = self._auto_sp, self._auto_sl
                    ep, el = self._auto_sp + chunk - 1, 25
                elif i == n - 1:
                    sp, sl = self._auto_sp + i * chunk, 1
                    ep, el = self._auto_ep, self._auto_el
                else:
                    sp, sl = self._auto_sp + i * chunk, 1
                    ep, el = self._auto_sp + (i+1) * chunk - 1, 25
                vp = self._build_video_page(i, n, sp, sl, ep, el)
                self._vpages.append(vp)

            self._build_confirm_page()
            self._show_page(1)
            return

        # Validate video page before moving forward
        if 1 <= idx <= self._n_videos:
            vp = self._stack.widget(idx)
            if not vp._path:
                QMessageBox.warning(self, 'No File Selected',
                    f'Please browse for Video {idx}.')
                return
            if not os.path.isfile(vp._path):
                QMessageBox.warning(self, 'File Not Found',
                    f'Cannot find:\n{vp._path}')
                return
            if (vp._sp.value(), vp._sl.value()) >= (vp._ep.value(), vp._el.value()):
                QMessageBox.warning(self, 'Invalid Range',
                    'Start must be before End.')
                return

        # Moving to confirm page: collect all video data and rebuild
        if idx == self._n_videos:
            self._video_data = []
            for vp in self._vpages:
                self._video_data.append({
                    'path': vp._path,
                    'sp':   vp._sp.value(),
                    'sl':   vp._sl.value(),
                    'ep':   vp._ep.value(),
                    'el':   vp._el.value(),
                })
            # Rebuild confirm page with current data
            confirm_idx = self._stack.count() - 1
            old = self._stack.widget(confirm_idx)
            self._stack.removeWidget(old); old.deleteLater()
            self._build_confirm_page()

        self._show_page(idx + 1)

    def _do_sync_now(self):
        self._collect_video_data()
        self._sync_now = True
        self.accept()

    def _do_later(self):
        self._collect_video_data()
        self._sync_now = False
        self.accept()

    def _collect_video_data(self):
        self._video_data = []
        for vp in (self._vpages if hasattr(self, '_vpages') else []):
            self._video_data.append({
                'path': vp._path,
                'sp':   vp._sp.value(),
                'sl':   vp._sl.value(),
                'ep':   vp._ep.value(),
                'el':   vp._el.value(),
            })

    def result_data(self):
        return {
            'video_data': self._video_data,
            'sync_now':   self._sync_now,
        }


# =============================================================================
# PROGRESS DIALOG
# =============================================================================

class ProgressDialog(QDialog):
    cancelled = pyqtSignal()

    def __init__(self, title, steps, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(640)
        self.setModal(True)
        self._t0      = time.time()
        self._current = ''

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14,12,14,10); lay.setSpacing(6)

        self._hdr = QLabel('Starting...')
        self._hdr.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        self._hdr.setStyleSheet('color:#5bc8ff;padding:4px 0;')
        lay.addWidget(self._hdr)

        self._rows = {}
        for s in steps:
            row = QHBoxLayout()
            lbl = QLabel(s); lbl.setFixedWidth(260)
            lbl.setStyleSheet('color:#555;font-size:11px;')
            bar = QProgressBar(); bar.setRange(0,100); bar.setValue(0)
            bar.setFixedHeight(16); bar.setFormat('%p%')
            row.addWidget(lbl); row.addWidget(bar)
            lay.addLayout(row)
            self._rows[s] = (lbl, bar)

        self._msg = QLabel('Please wait...')
        self._msg.setWordWrap(True)
        self._msg.setStyleSheet('color:#888;font-size:10px;padding:2px 0;')
        lay.addWidget(self._msg)

        self._elapsed_lbl = QLabel('Elapsed: 0:00')
        self._elapsed_lbl.setStyleSheet('color:#ffb74d;font-size:10px;')
        lay.addWidget(self._elapsed_lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color:#333;'); lay.addWidget(sep)

        note = QLabel('stable-ts forced alignment running.  '
                      'CPU: ~4 min/hr of audio.  GPU: ~1 min/hr.')
        note.setWordWrap(True)
        note.setStyleSheet('color:#666;font-size:10px;padding:3px 6px;'
                           'background:#1a1a1a;border-radius:3px;')
        lay.addWidget(note)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.clicked.connect(lambda: self.cancelled.emit())
        btn_row.addWidget(self._cancel_btn)
        lay.addLayout(btn_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    def _tick(self):
        e = int(time.time()-self._t0); m,s = divmod(e,60)
        self._elapsed_lbl.setText(f'Elapsed: {m}:{s:02d}')

    def set_step(self, name):
        self._current = name
        self._hdr.setText(name)
        for k,(lbl,bar) in self._rows.items():
            if k==name:
                lbl.setStyleSheet('color:#5bc8ff;font-size:11px;font-weight:bold;')
                bar.setStyleSheet('QProgressBar::chunk{background:#2196f3;}')
            elif bar.value()==100:
                lbl.setStyleSheet('color:#4caf50;font-size:11px;')

    def set_prog(self, pct, msg=''):
        if self._current in self._rows:
            self._rows[self._current][1].setValue(pct)
        if msg: self._msg.setText(msg)

    def complete_step(self):
        if self._current in self._rows:
            lbl,bar = self._rows[self._current]
            bar.setValue(100)
            lbl.setStyleSheet('color:#4caf50;font-size:11px;')


# =============================================================================
# SYNC WORKER
# =============================================================================

class SyncWorker(QThread):
    step      = pyqtSignal(str)
    step_done = pyqtSignal()
    prog      = pyqtSignal(int, str)
    done      = pyqtSignal()
    error     = pyqtSignal(str)

    def __init__(self, video_data, all_lines, model, language):
        super().__init__()
        self.video_data = video_data    # [{path,sp,sl,ep,el}, ...]
        self.all_lines  = all_lines
        self.model      = model
        self.language   = language
        self.video_dur  = 0.0

    def _get_lines(self, d):
        sp,sl,ep,el = d['sp'],d['sl'],d['ep'],d['el']
        return [l for l in self.all_lines
                if (l.page>sp or (l.page==sp and l.line_num>=sl))
                and (l.page<ep or (l.page==ep and l.line_num<=el))]

    def run(self):
        wavs = []
        try:
            from deposync.engine.extract import to_wav
            from deposync.engine.align   import run as align_run

            n = len(self.video_data)
            for i, d in enumerate(self.video_data):
                pfx = f'[Video {i+1}/{n}] ' if n > 1 else ''

                seg_lines = self._get_lines(d)
                if not seg_lines:
                    continue

                self.step.emit(f'{pfx}Extracting Audio')
                self.prog.emit(0, f'Extracting audio from {os.path.basename(d["path"])}...')
                wav = to_wav(d['path'])
                wavs.append(wav)

                try:
                    import soundfile as sf
                    with sf.SoundFile(wav) as f:
                        self.video_dur = len(f)/f.samplerate
                except Exception:
                    pass

                self.step_done.emit()
                self.step.emit(f'{pfx}Processing Audio')
                self.prog.emit(0, 'Starting forced alignment...')

                align_run(
                    audio_path=wav,
                    lines=seg_lines,
                    model_size=self.model,
                    language=self.language,
                    progress=lambda p,m: self.prog.emit(p,m),
                )
                self.step_done.emit()

            self.step.emit('Finalizing')
            self.prog.emit(50, 'Saving results...')
            try:
                log = os.path.join(os.path.expanduser('~'), 'DepoSync_log.txt')
                ts  = sum(1 for l in self.all_lines if l.timestamp_sec is not None)
                with open(log,'w',encoding='utf-8') as f:
                    f.write(f'DepoSync {ts}/{len(self.all_lines)} lines\n\n')
                    for l in self.all_lines:
                        f.write(f'{_hms(l.timestamp_sec) or "NO TS":15s}  '
                                f'p{l.page:03d}:{l.line_num:02d}  {l.text}\n')
            except Exception:
                pass
            self.prog.emit(100,'Complete.')
            self.step_done.emit()
            self.done.emit()

        except Exception as e:
            self.error.emit(f'{e}\n\n{_tb.format_exc()[:1200]}')
        finally:
            for w in wavs:
                try:
                    if os.path.exists(w): os.remove(w)
                except Exception: pass


# =============================================================================
# RESULTS DIALOG
# =============================================================================

class ResultsDialog(QDialog):
    export_requested = pyqtSignal()

    def __init__(self, lines, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Sync Complete -- Review Results')
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)

        total=len(lines); ts=sum(1 for l in lines if l.timestamp_sec is not None)
        green=sum(1 for l in lines if l.timestamp_sec and l.confidence>=CONF_GREEN)
        amber=sum(1 for l in lines if l.timestamp_sec and CONF_AMBER<=l.confidence<CONF_GREEN)
        red  =sum(1 for l in lines if l.timestamp_sec and l.confidence<CONF_AMBER)
        no_ts=total-ts; pct=ts*100//max(total,1)

        col='#4caf50' if pct>=90 else '#ffb74d' if pct>=75 else '#ef5350'
        hdr=QLabel(f'<b style="font-size:16px;">{ts}/{total} lines timestamped  ({pct}%)</b>')
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setStyleSheet(f'color:{col};padding:10px;background:#1a1a1a;border-radius:5px;')
        lay.addWidget(hdr)

        grp=QGroupBox('Results by Confidence  (Indata standard)')
        gl=QVBoxLayout(grp)
        for c,lbl,cnt in [
            ('#4caf50',f'? 97%  ?  {green} lines  ?  auto-approved (Green)',green),
            ('#ffb74d',f'70?97%  ?  {amber} lines  ?  review recommended',amber),
            ('#ef5350',f'< 70%  ?  {red} lines  ?  needs attention',red),
            ('#555',   f'No timestamp  ?  {no_ts} lines',no_ts),
        ]:
            row=QHBoxLayout(); dot=QLabel('?'); dot.setFixedWidth(20)
            dot.setStyleSheet(f'color:{c};font-size:16px;')
            lb=QLabel(lbl); lb.setStyleSheet(f'color:{c};')
            row.addWidget(dot); row.addWidget(lb); row.addStretch()
            gl.addLayout(row)
        lay.addWidget(grp)

        lay.addWidget(QLabel(
            '<span style="color:#888;font-size:10px;">'
            'Click Review to inspect timestamps in the table.<br>'
            'Click any row to jump the video to that timestamp.<br>'
            'Use TAP SYNC to manually correct lines.</span>'))

        btn_row=QHBoxLayout()
        b_rev=QPushButton('Review Sync')
        b_rev.setStyleSheet('background:#007acc;color:#fff;font-weight:bold;padding:6px 20px;')
        b_rev.clicked.connect(self.accept)

        b_exp=QPushButton('Export Now')
        b_exp.setStyleSheet('background:#2e7d32;color:#fff;font-weight:bold;padding:6px 20px;')
        b_exp.clicked.connect(lambda: (self.accept(), self.export_requested.emit()))

        b_cls=QPushButton('Close'); b_cls.clicked.connect(self.accept)
        btn_row.addWidget(b_rev); btn_row.addWidget(b_exp); btn_row.addWidget(b_cls)
        lay.addLayout(btn_row)


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('DepoSync  --  Legal Deposition Sync')
        self.setMinimumSize(1200,700); self.resize(1440,860)

        self._t_path      = ''
        self._lines       = []
        self._video_data  = []
        self._worker      = None
        self._prog_dlg    = None
        self._model       = 'base.en'
        self._language    = 'en'
        self._video_dur   = 0.0
        self._tap_mode    = False
        self._dur         = 0.0
        self._seeking     = False
        self._ef_installed = False

        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        # Install event filter AFTER window is shown - avoids Python 3.14 crash
        if not self._ef_installed:
            self._ef_installed = True
            QApplication.instance().installEventFilter(self)
        # Detect hardware after window shows
        QTimer.singleShot(300, self._detect_hw)

    def _build(self):
        tb = QToolBar(); tb.setMovable(False)
        self.addToolBar(tb)

        def _a(lbl,fn,tip=''):
            a=QAction(lbl,self); a.triggered.connect(fn)
            if tip: a.setToolTip(tip)
            tb.addAction(a); return a

        self._act_add    = _a('Add Transcript', self._add_transcript,
                               'Load transcript and set up videos')
        tb.addSeparator()
        self._act_sync   = _a('Sync Now', self._run_sync,
                               'Start forced alignment')
        tb.addSeparator()
        self._act_export = _a('Export', self._export,
                               'Save InData ASCII or XMEF')
        tb.addSeparator()
        _a('Settings', self._settings)

        self._hw_lbl = QLabel('  detecting...')
        self._hw_lbl.setStyleSheet('color:#5af;font-size:10px;padding:0 10px;')
        tb.addWidget(self._hw_lbl)

        # Splitter
        sp = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(sp)

        # LEFT: table
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(4,4,4,4)
        self._info=QLabel('Click  Add Transcript  to begin.')
        self._info.setStyleSheet('color:#888;font-size:10px;padding:2px;')
        ll.addWidget(self._info)
        self._prog_bar=QProgressBar(); self._prog_bar.setMaximumHeight(14)
        self._prog_bar.setVisible(False); ll.addWidget(self._prog_bar)
        self._prog_lbl=QLabel(''); self._prog_lbl.setStyleSheet('color:#5af;font-size:10px;')
        self._prog_lbl.setVisible(False); ll.addWidget(self._prog_lbl)

        self._tbl=QTableWidget(0,5)
        self._tbl.setHorizontalHeaderLabels(['Page','Line','Text','Timestamp','Conf'])
        self._tbl.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        for c in (0,1,3,4):
            self._tbl.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setFont(_mono()); self._tbl.setAlternatingRowColors(True)
        self._tbl.cellClicked.connect(self._row_clicked)
        ll.addWidget(self._tbl,1)
        self._summary=QLabel(''); self._summary.setStyleSheet('color:#666;font-size:10px;padding:2px;')
        ll.addWidget(self._summary)
        sp.addWidget(left)

        # RIGHT: player
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(4,4,4,4)
        self._has_player=False; self._player=None
        try:
            from deposync.ui.vlc_player import VLCPlayerWidget
            self._player=VLCPlayerWidget()
            self._player.position_changed.connect(self._on_pos)
            self._player.duration_changed.connect(self._on_dur)
            rl.addWidget(self._player,1); self._has_player=True
        except Exception as e:
            lbl=QLabel(f'Video player unavailable:\n{e}\n\nInstall python-vlc')
            lbl.setStyleSheet('color:#f88;padding:20px;')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(lbl,1)

        self._seek=QSlider(Qt.Orientation.Horizontal); self._seek.setRange(0,10000)
        self._seek.sliderPressed.connect(lambda: setattr(self,'_seeking',True))
        self._seek.sliderReleased.connect(self._do_seek)
        rl.addWidget(self._seek)

        tr=QHBoxLayout()
        self._t_lbl=QLabel('--:--:--'); self._t_lbl.setFont(_mono())
        self._t_lbl.setStyleSheet('color:#5af;font-size:13px;')
        tr.addWidget(self._t_lbl); tr.addStretch()
        self._d_lbl=QLabel('/ --:--:--')
        self._d_lbl.setStyleSheet('color:#555;font-size:10px;')
        tr.addWidget(self._d_lbl); rl.addLayout(tr)

        ctrl=QHBoxLayout()
        self._btn_rw=QPushButton('< 2s'); self._btn_rw.setFixedWidth(50)
        self._btn_play=QPushButton('Play'); self._btn_play.setFixedWidth(65)
        self._btn_ff=QPushButton('2s >'); self._btn_ff.setFixedWidth(50)
        self._btn_rw.clicked.connect(lambda: self._skip(-2))
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_ff.clicked.connect(lambda: self._skip(2))
        for b in (self._btn_rw,self._btn_play,self._btn_ff): ctrl.addWidget(b)
        ctrl.addWidget(QLabel('  Speed:'))
        self._spd=QSlider(Qt.Orientation.Horizontal)
        self._spd.setRange(25,300); self._spd.setValue(100); self._spd.setFixedWidth(100)
        self._spd_lbl=QLabel('1.0x'); self._spd_lbl.setFixedWidth(34)
        self._spd.valueChanged.connect(self._on_speed)
        ctrl.addWidget(self._spd); ctrl.addWidget(self._spd_lbl); ctrl.addStretch()
        rl.addLayout(ctrl)

        self._btn_tap=QPushButton('TAP SYNC')
        self._btn_tap.setCheckable(True)
        self._btn_tap.setToolTip('Video plays. SPACE=stamp. LEFT=rewind 2s. ESC=exit.')
        self._btn_tap.setStyleSheet(
            'QPushButton{background:#1a3a1a;color:#4f4;font-weight:bold;padding:5px 14px;}'
            'QPushButton:checked{background:#2d6a2d;color:#fff;}')
        self._btn_tap.toggled.connect(self._on_tap)
        rl.addWidget(self._btn_tap)

        sp.addWidget(right); sp.setSizes([780,460])
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('Ready.  Click Add Transcript to begin.')
        self._refresh()

    # ?? GPU detection ?????????????????????????????????????????????????????????

    def _detect_hw(self):
        try:
            from deposync.engine.align import detect_device
            dev,_,desc=detect_device()
            if dev=='cuda':
                self._hw_lbl.setText(f'  GPU: {desc}  ')
                self._hw_lbl.setStyleSheet('color:#4f4;font-weight:bold;font-size:10px;padding:0 10px;')
            else:
                short=desc.split('[')[0].strip()
                self._hw_lbl.setText(f'  {short}  ')
                self._hw_lbl.setStyleSheet('color:#fa4;font-size:10px;padding:0 10px;')
                self._hw_lbl.setToolTip(desc)
        except Exception: pass

    # ?? Add Transcript ? Setup Wizard ?????????????????????????????????????????

    def _add_transcript(self):
        p,_=QFileDialog.getOpenFileName(
            self,'Add Transcript','','Text Files (*.txt);;All Files (*)')
        if not p: return

        try:
            from deposync.parser.transcript import parse, auto_detect_range
            lines=parse(p)
        except Exception as e:
            QMessageBox.critical(self,'Parse Error',str(e)); return

        if not lines:
            QMessageBox.warning(self,'Empty',
                'No lines found. Check this is an InData/YesLaw ASCII .txt file.')
            return

        self._t_path=p; self._lines=lines
        sp,sl,ep,el=auto_detect_range(lines)

        self._populate_table()
        self._refresh()
        fp,lp=lines[0].page,lines[-1].page
        self._info.setText(
            f'{os.path.basename(p)}   {len(lines)} lines   pages {fp}?{lp}')
        self.statusBar().showMessage(f'Transcript loaded: {len(lines)} lines.')

        # Open wizard immediately
        wizard=SetupWizard(p,lines,sp,sl,ep,el,self)
        if wizard.exec()!=QDialog.DialogCode.Accepted: return

        data=wizard.result_data()
        self._video_data=data['video_data']

        if not self._video_data: return

        # Load first video into player
        if self._has_player:
            try: self._player.load(self._video_data[0]['path'])
            except Exception: pass

        names=', '.join(os.path.basename(d['path']) for d in self._video_data)
        self._info.setText(
            f'{os.path.basename(p)}   {len(lines)} lines   pages {fp}?{lp}   '
            f'?   {len(self._video_data)} video(s): {names}')
        self._refresh()

        if data['sync_now']:
            self._run_sync()

    # ?? Sync ??????????????????????????????????????????????????????????????????

    def _run_sync(self):
        if not self._lines:
            QMessageBox.warning(self,'No Transcript','Click Add Transcript first.'); return
        if not self._video_data:
            QMessageBox.warning(self,'No Videos',
                'No videos configured. Click Add Transcript to set them up.'); return

        # Pause video
        if self._has_player:
            try: self._player.pause(); self._btn_play.setText('Play')
            except Exception: pass

        # Build progress steps
        n=len(self._video_data); steps=[]
        for i in range(1,n+1):
            pfx=f'[Video {i}/{n}] ' if n>1 else ''
            steps+=[f'{pfx}Extracting Audio',f'{pfx}Processing Audio']
        steps.append('Finalizing')

        self._prog_dlg=ProgressDialog(
            f'Syncing  {os.path.basename(self._t_path)}',steps,self)
        self._prog_dlg.cancelled.connect(self._cancel_sync)
        self._prog_dlg.show()

        self._act_sync.setEnabled(False)
        self._worker=SyncWorker(self._video_data,self._lines,self._model,self._language)
        self._worker.step.connect(self._prog_dlg.set_step)
        self._worker.step_done.connect(self._prog_dlg.complete_step)
        self._worker.prog.connect(lambda p,m: self._prog_dlg.set_prog(p,m))
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel_sync(self):
        if self._worker and self._worker.isRunning(): self._worker.terminate()
        if self._prog_dlg: self._prog_dlg.accept(); self._prog_dlg=None
        self._act_sync.setEnabled(True)
        self.statusBar().showMessage('Sync cancelled.')

    def _on_done(self):
        self._video_dur=self._worker.video_dur
        self._act_sync.setEnabled(True)
        if self._prog_dlg: self._prog_dlg.accept(); self._prog_dlg=None
        self._populate_table(); self._refresh()
        ts=sum(1 for l in self._lines if l.timestamp_sec is not None)
        pct=ts*100//max(len(self._lines),1)
        self.statusBar().showMessage(f'Sync done: {ts}/{len(self._lines)} ({pct}%).')
        res=ResultsDialog(self._lines,self)
        res.export_requested.connect(self._export)
        res.exec()

    def _on_error(self,msg):
        self._act_sync.setEnabled(True)
        if self._prog_dlg: self._prog_dlg.accept(); self._prog_dlg=None
        self._refresh()
        QMessageBox.critical(self,'Sync Error',msg)

    # ?? Table ?????????????????????????????????????????????????????????????????

    def _populate_table(self):
        self._tbl.setUpdatesEnabled(False)
        self._tbl.setRowCount(len(self._lines))
        try:
            for row,l in enumerate(self._lines):
                has_ts=l.timestamp_sec is not None
                if l.manually_set:               bg,fg=C_MN_BG,C_MN_FG
                elif not has_ts:                 bg,fg=C_NO_BG,C_NO_FG
                elif l.confidence>=CONF_GREEN:   bg,fg=C_GN_BG,C_GN_FG
                elif l.confidence>=CONF_AMBER:   bg,fg=C_AM_BG,C_AM_FG
                else:                            bg,fg=C_RD_BG,C_RD_FG
                for col,val in enumerate([str(l.page),str(l.line_num),l.text,
                                          _hms(l.timestamp_sec),
                                          f'{l.confidence:.2f}' if has_ts else '']):
                    it=QTableWidgetItem(val)
                    it.setBackground(QBrush(bg)); it.setForeground(QBrush(fg))
                    self._tbl.setItem(row,col,it)
            self._tbl.verticalHeader().setDefaultSectionSize(20)
        finally:
            self._tbl.setUpdatesEnabled(True)
        ts=sum(1 for l in self._lines if l.timestamp_sec is not None)
        g=sum(1 for l in self._lines if l.timestamp_sec and l.confidence>=CONF_GREEN)
        a=sum(1 for l in self._lines if l.timestamp_sec and CONF_AMBER<=l.confidence<CONF_GREEN)
        if ts:
            self._summary.setText(
                f'  {ts}/{len(self._lines)} timestamped   Green={g}   Amber={a}   No TS={len(self._lines)-ts}')

    def _row_clicked(self,row,_col):
        if row<len(self._lines) and self._has_player:
            l=self._lines[row]
            if l.timestamp_sec is not None: self._player.seek(l.timestamp_sec)

    # ?? Export ????????????????????????????????????????????????????????????????

    def _export(self):
        if not any(l.timestamp_sec for l in self._lines):
            QMessageBox.warning(self,'Nothing to Export','Run a sync first.'); return
        cb=QComboBox()
        cb.addItem('Sanction / OnCue (.mdb)  --  OnCue, TrialDirector  [recommended]','mdb')
        cb.addItem('TimeCoder (.cms)  --  OnCue, Sanction','cms')
        cb.addItem('InData / YesLaw ASCII (.txt)  --  TimeCoder Pro, TrialDirector','ascii')
        cb.addItem('XMEF (.xmef)  --  TextMap, CaseMap, Relativity','xmef')
        dlg=QDialog(self); dlg.setWindowTitle('Export')
        ql=QVBoxLayout(dlg); ql.addWidget(QLabel('Format:')); ql.addWidget(cb)
        bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); ql.addWidget(bb)
        if dlg.exec()!=QDialog.DialogCode.Accepted: return
        fmt=cb.currentData()
        if fmt=='ascii':
            p,_=QFileDialog.getSaveFileName(self,'Save ASCII','','InData ASCII (*.txt)')
            if not p: return
            from deposync.export.ascii_export import write; n=write(self._lines,p)
        elif fmt in ('mdb','cms'):
            ext='mdb' if fmt=='mdb' else 'cms'
            cap='Save Sanction/OnCue MDB' if fmt=='mdb' else 'Save TimeCoder CMS'
            p,_=QFileDialog.getSaveFileName(self,cap,'',f'{ext.upper()} (*.{ext})')
            if not p: return
            if not p.lower().endswith('.'+ext): p+='.'+ext
            w=os.path.splitext(os.path.basename(self._t_path))[0].replace('_',' ')
            vp=self._video_data[0]['path'] if self._video_data else ''
            try:
                from deposync.export.sanction_mdb import write
                n=write(p,self._lines,witness=w,video_path=vp,
                        video_dur_sec=self._video_dur)
            except Exception as e:
                QMessageBox.critical(self,'MDB/CMS Export',
                    'Could not write the Access database.\n\n'
                    'This format needs the Microsoft Access Database Engine on '
                    'Windows. Install the free "Microsoft Access Database Engine '
                    '2016 Redistributable" (match your Python 32/64-bit), then '
                    'retry.\n\nDetails: '+str(e))
                return
        else:
            p,_=QFileDialog.getSaveFileName(self,'Save XMEF','','XMEF (*.xmef)')
            if not p: return
            w=os.path.splitext(os.path.basename(self._t_path))[0].replace('_',' ')
            vf=os.path.basename(self._video_data[0]['path']) if self._video_data else ''
            from deposync.export.xmef_export import write
            n=write(self._lines,p,witness=w,video_file=vf,video_dur_sec=self._video_dur)
        QMessageBox.information(self,'Exported',f'Saved {n} timestamped lines to:\n{p}')

    # ?? Settings ??????????????????????????????????????????????????????????????

    def _settings(self):
        dlg=QDialog(self); dlg.setWindowTitle('Settings')
        fl=QFormLayout(dlg)
        _M=[('base.en','Base -- recommended'),('small.en','Small -- more accurate'),
            ('medium.en','Medium -- most accurate'),('tiny.en','Tiny -- fastest')]
        mcb=QComboBox()
        for k,l in _M: mcb.addItem(l,k)
        for i in range(mcb.count()):
            if mcb.itemData(i)==self._model: mcb.setCurrentIndex(i)
        lang=QLineEdit(self._language)
        fl.addRow('Model:',mcb); fl.addRow('Language:',lang)
        fl.addRow(QLabel('<small style="color:#777">GPU: see README.txt</small>'))
        bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); fl.addRow(bb)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            self._model=mcb.currentData(); self._language=lang.text().strip() or 'en'

    # ?? Video controls ????????????????????????????????????????????????????????

    def _toggle_play(self):
        if not self._has_player: return
        if self._player.is_playing(): self._player.pause(); self._btn_play.setText('Play')
        else: self._player.play(); self._btn_play.setText('Pause')

    def _skip(self,s):
        if self._has_player: self._player.seek(max(0.0,self._player.get_position()+s))

    def _do_seek(self):
        self._seeking=False
        if self._has_player and self._dur>0:
            self._player.seek(self._seek.value()/10000.0*self._dur)

    def _on_pos(self,t):
        if not self._seeking and self._dur>0:
            self._seek.setValue(int(t/self._dur*10000))
        self._t_lbl.setText(_hms(t)[:8] if t else '--:--:--')

    def _on_dur(self,d):
        self._dur=d; h,m,s=int(d//3600),int((d%3600)//60),int(d%60)
        self._d_lbl.setText(f'/ {h:02d}:{m:02d}:{s:02d}')

    def _on_speed(self,v):
        spd=v/100.0; self._spd_lbl.setText(f'{spd:.1f}x')
        if self._has_player:
            try: self._player.set_rate(spd)
            except Exception: pass

    # ?? TAP SYNC ??????????????????????????????????????????????????????????????

    def eventFilter(self,obj,event):
        from PyQt6.QtCore import QEvent
        if not self._tap_mode or event.type()!=QEvent.Type.KeyPress:
            return super().eventFilter(obj,event)
        k=event.key()
        if   k==Qt.Key.Key_Space:  self._tap_stamp(); return True
        elif k==Qt.Key.Key_Left:   self._skip(-2); self._resume(); return True
        elif k==Qt.Key.Key_Escape: self._btn_tap.setChecked(False); return True
        return super().eventFilter(obj,event)

    def _on_tap(self,active):
        self._tap_mode=active
        self._btn_tap.setText('TAP SYNC  |  SPACE=stamp  LEFT=rewind  ESC=exit' if active else 'TAP SYNC')
        if active: self._resume()
        elif self._has_player:
            self._btn_play.setText('Pause' if self._player.is_playing() else 'Play')

    def _tap_stamp(self):
        if not self._has_player: return
        t=self._player.get_position()
        rows=sorted({i.row() for i in self._tbl.selectedItems()})
        if rows:
            row=rows[0]
            if row<len(self._lines):
                l=self._lines[row]; l.timestamp_sec=round(t,3)
                l.confidence=1.0; l.manually_set=True; self._update_row(row)
            nxt=rows[-1]+1
            if nxt<self._tbl.rowCount():
                self._tbl.selectRow(nxt)
                self._tbl.scrollTo(self._tbl.model().index(nxt,0),
                                    QAbstractItemView.ScrollHint.PositionAtCenter)
            else: self._btn_tap.setChecked(False)
        self._resume()

    def _resume(self):
        if self._has_player and not self._player.is_playing():
            self._player.play(); self._btn_play.setText('Pause')

    def _update_row(self,row):
        if row>=len(self._lines): return
        l=self._lines[row]; has_ts=l.timestamp_sec is not None
        if l.manually_set: bg,fg=C_MN_BG,C_MN_FG
        elif not has_ts:   bg,fg=C_NO_BG,C_NO_FG
        elif l.confidence>=CONF_GREEN: bg,fg=C_GN_BG,C_GN_FG
        else: bg,fg=C_AM_BG,C_AM_FG
        for col,val in enumerate([str(l.page),str(l.line_num),l.text,
                                   _hms(l.timestamp_sec),
                                   f'{l.confidence:.2f}' if has_ts else '']):
            it=self._tbl.item(row,col) or QTableWidgetItem(val)
            it.setText(val); it.setBackground(QBrush(bg)); it.setForeground(QBrush(fg))
            self._tbl.setItem(row,col,it)

    def _refresh(self):
        has_t=bool(self._lines); has_v=bool(self._video_data)
        has_r=has_t and any(l.timestamp_sec for l in self._lines)
        self._act_sync.setEnabled(has_t and has_v)
        self._act_export.setEnabled(has_r)
        self._btn_tap.setEnabled(has_t)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    _write_ok()
    try:
        for base in [r'C:\DepoSync',
                     os.path.join(os.environ.get('APPDATA',''),'DepoSync')]:
            try:
                for sub in ('models','exports','logs'):
                    os.makedirs(os.path.join(base,sub),exist_ok=True)
                break
            except Exception: continue

        app=QApplication(sys.argv)
        app.setStyle('Fusion')
        pal=QPalette()
        for role,col in [
            (QPalette.ColorRole.Window,          QColor(24,24,24)),
            (QPalette.ColorRole.WindowText,      QColor(215,215,215)),
            (QPalette.ColorRole.Base,            QColor(14,14,14)),
            (QPalette.ColorRole.AlternateBase,   QColor(20,20,20)),
            (QPalette.ColorRole.Text,            QColor(215,215,215)),
            (QPalette.ColorRole.Button,          QColor(40,40,40)),
            (QPalette.ColorRole.ButtonText,      QColor(215,215,215)),
            (QPalette.ColorRole.Highlight,       QColor(0,115,200)),
            (QPalette.ColorRole.HighlightedText, QColor(255,255,255)),
        ]:
            pal.setColor(role,col)
        app.setPalette(pal)

        win=MainWindow()
        win.show()
        sys.exit(app.exec())

    except Exception as e:
        _write_crash(_tb.format_exc())
        raise

if __name__=='__main__':
    main()
