# DepoSync — Product Requirements & Status

## Original problem statement
DepoSync is a Python **desktop app (PyQt6)** for synchronizing legal deposition
transcripts to video using `stable-ts` / `faster-whisper`. Goal: match
professional tools (InData TimeCoder Pro / YesLaw) — GPU auto-detect, range
resync, manual sync, exhibit linking, reliable exports, and a first-run setup
wizard for local dependencies.

> NOTE: This is a **local desktop app**, NOT a web service. The PyQt6 GUI
> cannot run on the headless Linux/ARM pod. Test non-GUI logic with `python -c`
> import/functional checks. The `/app/backend` FastAPI app exists ONLY to serve
> the source ZIP as a download link in the preview env.

## Architecture (/app/DepoSync)
```
DepoSync/
├── README.txt, DEPLOY.txt        # run + EXE-build instructions (user-facing)
├── INSTALL.bat, DepoSync.bat     # Windows launch scripts
├── requirements.txt, .gitignore
└── deposync/
    ├── config.py                 # paths + bootstrap config (appdata pointer)
    ├── models.py                 # Line, Word, Exhibit, line_to/from_dict
    ├── engine/  (extract.py, align.py)      # ffmpeg->wav, stable-ts alignment
    ├── parser/  (transcript.py, exhibits.py, page_image.py)
    ├── export/  (ascii_export.py, xmef_export.py)
    ├── setup/   (bootstrap.py, dictionaries.py)
    ├── storage/ (jobs.py)        # SQLite job library
    └── ui/      (main.py, vlc_player.py)     # PyQt6 GUI + VLC playback
```

## Current state (verified Feb 2026 fork)
- All non-GUI modules import cleanly; exhibit detection, SQLite job
  save/load/list, ASCII export, XMEF export all functionally verified.
- Exports present: **Sanction/OnCue (.mdb)**, **TimeCoder (.cms)**, **ASCII (.txt)**, **TextMap (.xmef)**.

## Resolved this session (Feb 2026)
1. **GitHub delivery failure (P0)** — ROOT CAUSE: git tracked only compiled
   `.pyc` bytecode; every `.py` source file was untracked, so "Save to GitHub"
   pushed no usable code. Fix: added `.gitignore`, untracked all `.pyc`, staged
   all source. HEAD now has all `.py`, 0 `.pyc`, 0 untracked.
2. **Direct ZIP download** — `/app/backend/server.py` serves a clean source ZIP
   at `{PREVIEW}/api/download/DepoSync_Source.zip` (verified externally, 200,
   application/zip, integrity OK). Root URL shows a download landing page.
3. **Runtime bug (lost source)** — `models.py` was missing `Exhibit`,
   `line_to_dict`, `line_from_dict` (imported by `exhibits.py` + `jobs.py`);
   crashed on import. Reconstructed precisely from usage; verified.
4. **MDB/CMS export REBUILT** — `export/sanction_mdb.py` writes the Jet/Access
   Info/Main/MPEGS schema reverse-engineered from the user's real sample .mdb
   (timecode truncated to whole seconds, PG markers per page, continuous Index).
   Pure-Python row-building is unit-tested (`tests/test_sanction_mdb.py`, 6
   tests) + validated on the real 4422-line transcript. Wired into the Export
   dialog (.mdb recommended, .cms same schema). Jet WRITE uses pywin32/ADOX
   (Windows only) — added `pywin32` to requirements + INSTALL.bat.
5. Added `README.txt` (run steps) + `DEPLOY.txt` (PyInstaller EXE build).

## Known gaps / backlog
- **MUST TEST ON WINDOWS**: the .mdb/.cms Jet *file write* can't run on the
  Linux pod (needs MS Access Database Engine / ACE OLE DB). Row logic verified;
  file write needs user validation. Error dialog guides to the free ACE
  redistributable if the provider is missing.
- The real `.cms` sample used a different OLE-blob Sanction schema (timecodes in
  binary blobs) — impractical/unreliable to replicate; OnCue recommends `.mdb`.
  We emit the proven Info/Main/MPEGS layout for both extensions.
- **YesLaw flow**: ALREADY implemented in current `ui/main.py` (`_add_transcript`
  opens SetupWizard → associate video(s) → sync). User's complaint was against a
  stale build they couldn't download. No preset exhibit count in current UI.
- **P1: Verify manual-sync UX** — spacebar stamping at 0.5x–3x (needs Windows run).
- **P2: Exhibit linking not wired into main UI** (`parser/exhibits.py` exists).
- Some handoff-listed files never existed on disk (tools/, installer/,
  setup_wizard.py, job_library.py, cli.py) — scrapped iteration.

## v0.6 (Feb 2026) — sync actually finishes + range picker + playback fixes
- **FFmpeg "-22 / never finished" FIXED**: align now pre-decodes the extracted
  WAV into a float32 numpy array (soundfile) and feeds THAT to stable-ts,
  bypassing faster-whisper's internal ffmpeg s16le pipe that emitted "Error
  submitting a packet to the muxer / Error writing trailer (-22)" and stalled
  the run. Also avoids decoding twice. `extract.py` hardened: config ffmpeg
  path, `-vn`, explicit `pcm_s16le`, size check.
- **Audio/video no longer plays during sync**: VLC `load()` no longer auto-plays;
  added real `stop()` + `set_mute()`; `pause/play` use explicit `set_pause`
  (libVLC `pause()` only toggled, unreliable). `_run_sync` now `stop()`+mutes;
  `_on_done` reloads paused + unmutes for review.
- **Speed**: CTranslate2 now uses all CPU threads (`cpu_threads=os.cpu_count()`).
  Note: AI forced-alignment is inherently heavier than InData/YesLaw (which read
  the videographer's burned-in timecode / manual sync, no AI). For a big speedup
  users can pick "Tiny -- fastest" in Settings (adequate for forced alignment of
  known text), or use NVIDIA GPU (~5x). AMD GPUs unsupported by the engine.
- **Range picker (requested UX)**: wizard video page replaced spinboxes with a
  searchable transcript list -> click a line + "Set as START" / "Set as END",
  per video. Data stored as plain ints (`vp._sp/_sl/_ep/_el`).
- Version bumped to **v0.6** (title bar).

## v0.7 (Feb 2026) — Fast waveform sync (the real fix for speed)
- **Root problem**: the app ran Whisper AI forced-alignment over the ENTIRE
  audio (~15-30 min on CPU, often never finishing). InData/YesLaw are fast
  because they do NOT use AI. AMD GPUs can't accelerate Whisper (CTranslate2 =
  CUDA/CPU only), so it was stuck on CPU.
- **NEW default engine `engine/align_fast.py`**: waveform-based sync — energy
  VAD finds speech vs silence (handles breaks/recesses), then distributes
  transcript lines across the speech timeline weighted by spoken-character
  count. Thresholds derived per-file from its own energy distribution -> works
  on ANY deposition, no per-job tuning.
  - TESTED on the user's real 3.6-hour audio (AS033126_synclync.wav, 218 min):
    **2.3-2.7 sec**, 100% of 4395 lines timestamped, last line "concluded at
    2:47 p.m." mapped to 03:37:51 (end of audio). GPU-independent.
  - Approximate (confidence 0.80 -> amber/"review"); user refines hot spots
    with TAP SYNC. Every line gets a timestamp (blank/marker lines filled).
- **Settings** now has a "Sync engine" choice: Fast (default) vs Precise (AI
  Whisper, slow, word-accurate). Toolbar label shows "Engine: Fast waveform
  sync (no GPU needed)" so the old CPU/AMD confusion is gone for default mode.
- Progress is now REAL (fast sync emits true progress, not a fake timer).
- Version -> v0.7.
- FUTURE (if word-accurate + fast is needed on AMD): whisper.cpp Vulkan or
  ONNX+DirectML can use AMD GPUs on Windows — not yet integrated.

## v0.8 (Feb 2026) — review workflow, exhibits, debug log, WAV-next-to-video
- **Debug log** (`deposync/debuglog.py`): plain-text trace to
  `~/DepoSync_debug.log` AND `<video folder>/DepoSync_debug.log`, timestamped
  with elapsed seconds. Logs app start, job setup, every sync step, `_on_done`
  stages, and exceptions — so a stall can be pinpointed (addresses "it froze").
- **WAV next to video + reuse**: `extract.to_wav` now writes
  `<videobase>_synclync.wav` beside the video (matches the user's own naming)
  and REUSES it if present (instant re-sync). Temp fallback if folder not
  writable. Timecodes always = video timeline. Worker no longer deletes the
  companion WAV.
- **Meaningful confidence scoring** (InData-style): fast sync now scores each
  line by distance to a detected speech ONSET — green (>=.90, snapped to a clear
  speech start), amber (.70-.90), red (<.70, interpolated). On the real 218-min
  job: 2737 green / 1546 amber / 112 red (was uniform 0.80). `CONF_GREEN`
  lowered 0.97->0.90 so the table colors match. ResultsDialog shows the
  breakdown; "Review Sync" leads to manual/range correction.
- **Add Exhibits button** + dialog: auto-detects exhibit references (22 found in
  sample), "Link Files..." attaches documents by filename number. XMEF export
  now writes exhibit Annotations AND bundles the actual files under `Exhibits/`
  in the .xmef. Stored on `self._exhibits`.
- Version -> v0.8. Tests: 8 pytest pass (added `test_xmef_exhibits.py`).
- Verified end-to-end on the user's real audio: fast sync 2.5s, 100% lines,
  scoring distribution, exhibits, XMEF-with-exhibits all good.

## v0.9 (Feb 2026) — FIXED the freeze (virtualized results grid)
- **Root cause (proven by the user's own debug log)**: sync ALWAYS worked
  perfectly — `align_fast: DONE 4321/4321 ts (100%), 2679 green, total=0.4s`.
  The GUI then went "Not Responding" at `_on_done: populating table (4422
  rows)...`. The old `_populate_table` built 4422 x 5 = ~22,000 QTableWidgetItem
  + ~44,000 QBrush on the main thread -> froze. That's why the user "never got
  to check it / no scoring system" — the freeze happened BEFORE the
  ResultsDialog could show.
- **Fix**: replaced QTableWidget with a virtualized `LineTableModel`
  (QAbstractTableModel) + QTableView. Only visible rows are rendered, so
  populate is O(1) (`beginResetModel/endResetModel`) and instant for any size.
  Colors come from `data()` BackgroundRole/ForegroundRole via `_line_colors`.
  Updated `_populate_table`, `_row_clicked(index)`, `_tap_stamp`
  (selectionModel), `_update_row` (model.row_changed) accordingly.
- ResultsDialog (scoring screen) now appears after sync; Review Sync + TAP SYNC
  work against the model. Fixed its legend text (97->90% to match CONF_GREEN).
- crash log review: only "Started OK" entries -> it was a freeze, not a crash.
- Version -> v0.9. 8 pytest pass.
- NOTE: PyQt6 cannot be built on the Linux/ARM pod, so the GUI fix is verified
  by code review + the model is the standard fix; user validates on Windows.

## Delivery to user
- Direct download: `{PREVIEW_URL}/api/download/DepoSync_Source.zip`
- OR "Save to GitHub" (now fixed to include all `.py`).

## v0.5 (Feb 2026) — UI/flow fixes from Windows screenshot
- **VERSION shown** in window title (`DepoSync v0.5`) so the user can confirm an
  update actually took effect. Version constant in `deposync/__init__.py`.
- **Wizard flow bug FIXED**: on Step 1 the stack had only 1 page, so `is_last`
  was wrongly True -> it showed "Sync Now"/"Later" instead of "Next". Clicking
  the blue "Sync Now" accepted with ZERO videos, so the app never asked for the
  video file. Fixed `_show_page`: `is_last = (idx==total) and idx!=0`. Step 1 now
  shows "Next >" -> video Browse page -> confirm -> Sync.
- **Garbled "?" characters FIXED**: source literally contained `?` (em-dashes /
  arrows / bullets lost in a prior bad encoding round-trip). Replaced all
  user-visible ones with safe ASCII; confidence-legend dot is now a CSS colored
  circle (no glyph).
- **AMD/CPU clarified**: faster-whisper (CTranslate2) supports NVIDIA CUDA or CPU
  only — AMD GPUs are NOT accelerated, so CPU is correct/expected. Removed the
  misleading "install ROCm PyTorch" message (ROCm wheels are Linux-only) from
  both the hardware label (`engine/align.py`) and `INSTALL.bat`.
- Verified: syntax, version import, 6 pytest pass, mojibake sweep clean, zip
  download (HTTP 200). GUI itself must be confirmed on Windows (no display here).
