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
- Exports present: **ASCII timecoded text (.txt)** and **TextMap (.xmef)**.

## Resolved this session (Feb 2026)
1. **GitHub delivery failure (P0)** — ROOT CAUSE: git was tracking only the
   compiled `.pyc` bytecode; every real `.py` source file was untracked, so
   "Save to GitHub" pushed no usable code. Fix: added `.gitignore`, untracked
   all `.pyc`/`__pycache__`, staged all 21 `.py` source files. Now 27 DepoSync
   files tracked, 0 untracked, 0 `.pyc`.
2. **Direct ZIP download** — `/app/backend/server.py` serves a clean source ZIP
   at `{PREVIEW}/api/download/DepoSync_Source.zip` (verified externally, 200,
   application/zip, integrity OK). Root URL shows a download landing page.
3. **Runtime bug (lost source)** — `models.py` was missing `Exhibit`,
   `line_to_dict`, `line_from_dict` (imported by `exhibits.py` + `jobs.py`);
   these crashed on import. Reconstructed precisely from usage; verified.
4. Added `README.txt` (run steps) + `DEPLOY.txt` (PyInstaller EXE build).

## Known gaps / backlog
- **P1: OnCue MDB/CMS export missing.** Original spec lists `.mdb/.cms` (OnCue)
  export. Earlier `cms_export.py` / `sanction_mdb.py` source was lost (only
  leftover `.pyc`, not referenced anywhere). Current app only does ASCII + XMEF.
  Needs rebuild if user still wants OnCue export.
- **P1: Verify manual-sync UX** — spacebar timecode stamping at 0.5x–3x
  playback wired in GUI (`ui/main.py` + `ui/vlc_player.py`). Needs a Windows
  PyQt6 run to confirm (cannot test on pod).
- **P1: YesLaw-style job flow** — user wants opening a transcript to prompt for
  associating video; exhibits should not preset a fixed amount. Review needed.
- Some handoff-listed files don't exist on disk (tools/ harnesses, installer/,
  setup_wizard.py, job_library.py, cli.py) — likely from a scrapped iteration.

## Delivery to user
- Direct download: `{PREVIEW_URL}/api/download/DepoSync_Source.zip`
- OR "Save to GitHub" (now fixed to include all `.py`).
