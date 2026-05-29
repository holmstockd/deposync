# -*- coding: utf-8 -*-
"""
Sanction / OnCue MDB (and CMS) export.

Produces a Microsoft Access (Jet 4.0) database with the *exact* schema used by
inData TimeCoder Pro / Sanction synchronized-transcript files, reverse-engineered
from real sample files:

    Info   (1 row)   deposition metadata
    MPEGS  (1+ rows) the associated video file(s)
    Main   (N rows)  one row per transcript line + a "PG" marker per page,
                     carrying the synchronized video Timecode (seconds)

OnCue, TrialDirector and Sanction import this .mdb directly and treat it as a
synchronized transcript. The same content is written for a .cms file (TimeCoder
Pro's native .cms uses this same Info/Main/MPEGS layout); OnCue recommends .mdb.

NOTE ON PLATFORM
----------------
Writing a Jet/Access database requires the Microsoft OLE DB provider, which only
exists on Windows (ACE.OLEDB.12.0 from the free "Access Database Engine"
redistributable, or the built-in Jet.OLEDB.4.0). The row-building logic below is
pure-Python and unit-tested; the actual file write uses pywin32 at runtime on the
user's Windows machine.
"""
from __future__ import annotations

import os
from datetime import date
from typing import List, Dict, Any, Optional

from deposync.models import Line

LINES_PER_PAGE_DEFAULT = 25


# --------------------------------------------------------------------------- #
# Pure helpers (cross-platform, unit-tested)
# --------------------------------------------------------------------------- #
def _hms(seconds: Optional[float]) -> str:
    """'HH:MM:SS' clock string for the TimeStamp text column ('' if unsynced)."""
    if seconds is None:
        return ""
    s = int(seconds)   # truncate to whole seconds, matching sample files
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def split_name(witness: str) -> Dict[str, str]:
    """
    Best-effort first/last name split from a witness/file label.
    Accepts 'Last, First ...' or 'First Last ...'.
    """
    w = (witness or "").strip()
    # strip trailing date-ish tokens (e.g. "3.31.2026")
    tokens = [t for t in w.replace(",", " , ").split() if t]
    if "," in w:
        last = w.split(",", 1)[0].strip()
        rest = w.split(",", 1)[1].strip().split()
        first = rest[0] if rest else ""
        return {"first": first, "last": last}
    words = [t for t in tokens if t != ","]
    if len(words) >= 2:
        return {"first": words[0], "last": words[1]}
    return {"first": "", "last": w}


def build_main_rows(lines: List[Line]) -> List[Dict[str, Any]]:
    """
    Build the Main-table rows from transcript lines.

    Emits a 'PG' marker row at every new page (LineNum 0, Text 'Page N'),
    then one 'LN' row per transcript line carrying the synced Timecode.
    Index increments across every row, matching the sample files.
    """
    rows: List[Dict[str, Any]] = []
    idx = 0
    prev_page = None
    for ln in lines:
        if ln.page != prev_page:
            idx += 1
            rows.append({
                "Index": idx, "Timecode": None, "TimeStamp": "", "Temp": "PG",
                "PageNum": ln.page, "LineNum": 0, "NoDisplay": False,
                "Text": f"Page {ln.page}", "Native": "", "Redact": False,
            })
            prev_page = ln.page
        idx += 1
        rows.append({
            "Index": idx,
            "Timecode": (float(ln.timestamp_sec)
                         if ln.timestamp_sec is not None else None),
            "TimeStamp": _hms(ln.timestamp_sec),
            "Temp": "LN",
            "PageNum": ln.page,
            "LineNum": ln.line_num,
            "NoDisplay": False,
            "Text": (ln.text or "")[:120],
            "Native": "",
            "Redact": False,
        })
    return rows


def build_tables(lines: List[Line],
                 witness: str = "",
                 depo_date: str = "",
                 video_path: str = "",
                 video_dur_sec: float = 0.0,
                 lines_per_page: int = LINES_PER_PAGE_DEFAULT
                 ) -> Dict[str, List[Dict[str, Any]]]:
    """Build all three tables (Info / MPEGS / Main) as plain row dicts."""
    pages = [ln.page for ln in lines] or [1]
    start_page, end_page = min(pages), max(pages)
    name = split_name(witness)
    depo_date = depo_date or date.today().strftime("%m/%d/%Y")

    vid_base = os.path.basename(video_path) if video_path else ""
    vid_id = os.path.splitext(vid_base)[0] if vid_base else ""
    media_group = (f"{name['last']}, {name['first']} (Vol. 01) - {depo_date}"
                   if (name["last"] or name["first"]) else "Volume 01")

    info = [{
        "Index": 1, "MediaGroup": "", "SourceCase": "",
        "FirstName": name["first"], "LastName": name["last"],
        "Date": depo_date, "StartPage": start_page, "EndPage": end_page,
        "LinesPerPage": lines_per_page, "Complete": True,
    }]

    mpegs = [{
        "Index": 1, "MediaGroup": media_group, "ID": vid_id,
        "FullPath": video_path or "", "Duration": float(video_dur_sec or 0.0),
        "Offset": 0.0,
    }] if video_path else []

    return {"Info": info, "MPEGS": mpegs, "Main": build_main_rows(lines)}


# --------------------------------------------------------------------------- #
# Jet/Access DDL + writer (Windows only, via pywin32)
# --------------------------------------------------------------------------- #
_TABLE_DDL = {
    "Info": """CREATE TABLE Info (
        [Index] LONG, MediaGroup TEXT(250), SourceCase TEXT(250),
        FirstName TEXT(250), LastName TEXT(250), [Date] TEXT(250),
        StartPage LONG, EndPage LONG, LinesPerPage LONG, Complete BIT)""",
    "Main": """CREATE TABLE Main (
        [Index] LONG, Timecode SINGLE, [TimeStamp] TEXT(8), Temp TEXT(2),
        PageNum LONG, LineNum LONG, NoDisplay BIT, [Text] TEXT(120),
        Native TEXT(120), Redact BIT)""",
    "MPEGS": """CREATE TABLE MPEGS (
        [Index] LONG, MediaGroup TEXT(250), ID TEXT(250), FullPath TEXT(250),
        Duration SINGLE, Offset SINGLE)""",
}

# Column order used when inserting via a Recordset.
_COLS = {
    "Info": ["Index", "MediaGroup", "SourceCase", "FirstName", "LastName",
             "Date", "StartPage", "EndPage", "LinesPerPage", "Complete"],
    "Main": ["Index", "Timecode", "TimeStamp", "Temp", "PageNum", "LineNum",
             "NoDisplay", "Text", "Native", "Redact"],
    "MPEGS": ["Index", "MediaGroup", "ID", "FullPath", "Duration", "Offset"],
}

_PROVIDERS = ("Microsoft.ACE.OLEDB.12.0", "Microsoft.Jet.OLEDB.4.0")


def _create_jet_db(path: str):
    """Create an empty Jet .mdb and return an open ADODB connection."""
    import pythoncom  # noqa: F401  (ensures COM is available)
    import win32com.client

    if os.path.exists(path):
        os.remove(path)

    last_err = None
    for provider in _PROVIDERS:
        try:
            cat = win32com.client.Dispatch("ADOX.Catalog")
            cat.Create(f"Provider={provider};Data Source={path};")
            conn = win32com.client.Dispatch("ADODB.Connection")
            conn.Open(f"Provider={provider};Data Source={path};")
            return conn
        except Exception as e:   # try next provider
            last_err = e
    raise RuntimeError(
        "Could not create the Access database. Install the free "
        "'Microsoft Access Database Engine 2016 Redistributable' "
        f"(matching your Python bitness). Underlying error: {last_err}")


def _insert_rows(conn, table: str, rows: List[Dict[str, Any]]):
    import win32com.client
    if not rows:
        return
    rs = win32com.client.Dispatch("ADODB.Recordset")
    rs.Open(table, conn, 1, 3, 2)               # adOpenKeyset, adLockOptimistic, adCmdTable
    cols = _COLS[table]
    for row in rows:
        rs.AddNew()
        for c in cols:
            v = row.get(c)
            if v is None:
                continue                        # leave Null (e.g. unsynced Timecode)
            rs.Fields(c).Value = v
        rs.Update()
    rs.Close()


def write(path: str,
          lines: List[Line],
          witness: str = "",
          depo_date: str = "",
          video_path: str = "",
          video_dur_sec: float = 0.0,
          lines_per_page: int = LINES_PER_PAGE_DEFAULT) -> int:
    """
    Write a Sanction/OnCue .mdb (or .cms) database.

    Returns the number of synchronized (timecoded) lines written.
    Raises RuntimeError on non-Windows systems or when no Access OLE DB
    provider is available.
    """
    tables = build_tables(lines, witness=witness, depo_date=depo_date,
                          video_path=video_path, video_dur_sec=video_dur_sec,
                          lines_per_page=lines_per_page)

    conn = _create_jet_db(path)
    try:
        for name, ddl in _TABLE_DDL.items():
            conn.Execute(ddl)
        for name in ("Info", "MPEGS", "Main"):
            _insert_rows(conn, name, tables[name])
    finally:
        try:
            conn.Close()
        except Exception:
            pass

    return sum(1 for r in tables["Main"]
               if r["Temp"] == "LN" and r["Timecode"] is not None)
