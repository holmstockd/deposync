============================================================
 DepoSync - Deposition Transcript / Video Sync
 HOW TO RUN ON YOUR WINDOWS PC
============================================================

You need Python 3.11 (64-bit) installed.
   Download: https://www.python.org/downloads/release/python-3119/
   IMPORTANT: During install, tick "Add python.exe to PATH".

------------------------------------------------------------
STEP 1 - INSTALL DEPENDENCIES (run once)
------------------------------------------------------------
1. Unzip this folder somewhere simple, e.g.  C:\DepoSync
2. Double-click  INSTALL.bat
   - It auto-detects your GPU (NVIDIA / AMD / CPU) and installs
     the correct PyTorch build, plus all Python packages.
   - This can take several minutes the first time.

You also need FFmpeg on your PC (used to pull audio from video):
   https://www.gyan.dev/ffmpeg/builds/  ->  "release essentials"
   Unzip and either add its \bin folder to PATH, or drop ffmpeg.exe
   next to the app. (The first-run setup can also help locate it.)

------------------------------------------------------------
STEP 2 - START THE APP
------------------------------------------------------------
Double-click  DepoSync.bat
   (or run:  python deposync\ui\main.py  )

------------------------------------------------------------
TYPICAL WORKFLOW
------------------------------------------------------------
1. Create / open a Job.
2. Load your transcript (E-Transcript / ASCII / .txt).
3. Associate the deposition video(s) with the job.
4. Run Sync  -> Whisper aligns each transcript line to a timecode.
5. Review / fix timings (Manual Sync, Range Re-sync).
6. Link exhibit files (auto-matched by exhibit number).
7. Export:
      - Sanction / OnCue (.mdb)  <-- recommended for OnCue & TrialDirector
      - TimeCoder (.cms)
      - ASCII timecoded text (.txt)
      - TextMap (.xmef)

   NOTE on .mdb / .cms: these are Microsoft Access databases. Writing them
   needs the Access engine on your PC. If export fails, install the FREE
   "Microsoft Access Database Engine 2016 Redistributable" (pick the version
   matching your Python: 64-bit Python -> 64-bit engine), then retry.
   INSTALL.bat already installs the required pywin32 package.

------------------------------------------------------------
DEBUG LOG (if something goes wrong)
------------------------------------------------------------
DepoSync writes a plain-text trace to:
   - your home folder:        %USERPROFILE%\DepoSync_debug.log
   - next to the video:       <video folder>\DepoSync_debug.log
Open it in Notepad and send it over if a sync stalls -- it shows every step
with timing so the problem can be pinpointed.

------------------------------------------------------------
AUDIO FILE (next to the video)
------------------------------------------------------------
On first sync, the audio is extracted next to the video as
<videoname>_synclync.wav. It is reused on later syncs (instant), and you can
keep or delete it. Timecodes always refer to the VIDEO timeline.

------------------------------------------------------------
EXHIBITS
------------------------------------------------------------
Click "Add Exhibits" on the toolbar. Exhibits referenced in the transcript are
detected automatically; use "Link Files..." to attach the documents (matched by
the number in the filename). Linked exhibits are written into the XMEF export
(and the files are bundled inside it).

* First run downloads the Whisper model (one-time).
* GPU is auto-detected; CPU also works (slower).
* Need a single .exe instead of Python? See "Building an EXE"
  in DEPLOY.txt (PyInstaller).

Questions / issues: keep this folder intact (the deposync\
package layout must stay as-is for imports to work).
