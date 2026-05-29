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

## Delivery to user
- Direct download: `{PREVIEW_URL}/api/download/DepoSync_Source.zip`
- OR "Save to GitHub" (now fixed to include all `.py`).
