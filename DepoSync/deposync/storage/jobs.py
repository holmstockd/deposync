# -*- coding: utf-8 -*-
"""
Job library -- persistent storage so users can reload past syncs.

Backed by SQLite in <install>/jobs/jobs.db. Each job stores its transcript path,
video configuration, exhibits, settings, sync stats and the full per-line
results (timestamps + confidence) so a job reopens exactly as it was left.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from deposync.config import CONFIG
from deposync.models import Line, Exhibit, line_to_dict, line_from_dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    path = CONFIG.jobs_dir / 'jobs.db'
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            transcript    TEXT,
            created       TEXT,
            updated       TEXT,
            total_lines   INTEGER DEFAULT 0,
            synced_lines  INTEGER DEFAULT 0,
            data          TEXT
        )""")
    return conn


def save_job(name: str,
             transcript_path: str,
             lines: List[Line],
             videos: List[Dict[str, Any]],
             exhibits: Optional[List[Exhibit]] = None,
             settings: Optional[Dict[str, Any]] = None,
             job_id: Optional[str] = None) -> str:
    """Insert or update a job. Returns the job id."""
    job_id = job_id or uuid.uuid4().hex
    total = len(lines)
    synced = sum(1 for l in lines if l.timestamp_sec is not None)
    payload = {
        'videos': videos or [],
        'exhibits': [e.to_dict() for e in (exhibits or [])],
        'settings': settings or {},
        'lines': [line_to_dict(l) for l in lines],
    }
    conn = _db()
    try:
        existing = conn.execute('SELECT id, created FROM jobs WHERE id=?',
                                (job_id,)).fetchone()
        created = existing['created'] if existing else _now()
        conn.execute("""
            INSERT INTO jobs (id,name,transcript,created,updated,
                              total_lines,synced_lines,data)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, transcript=excluded.transcript,
                updated=excluded.updated, total_lines=excluded.total_lines,
                synced_lines=excluded.synced_lines, data=excluded.data
        """, (job_id, name, transcript_path, created, _now(),
              total, synced, json.dumps(payload)))
        conn.commit()
    finally:
        conn.close()
    return job_id


def list_jobs() -> List[Dict[str, Any]]:
    """Lightweight metadata for the job library list (newest first)."""
    conn = _db()
    try:
        rows = conn.execute(
            'SELECT id,name,transcript,created,updated,total_lines,synced_lines '
            'FROM jobs ORDER BY updated DESC').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Full job incl. reconstructed Line/Exhibit objects."""
    conn = _db()
    try:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    data = json.loads(row['data'] or '{}')
    return {
        'id': row['id'],
        'name': row['name'],
        'transcript': row['transcript'],
        'created': row['created'],
        'updated': row['updated'],
        'videos': data.get('videos', []),
        'settings': data.get('settings', {}),
        'lines': [line_from_dict(d) for d in data.get('lines', [])],
        'exhibits': [Exhibit.from_dict(d) for d in data.get('exhibits', [])],
    }


def delete_job(job_id: str) -> bool:
    conn = _db()
    try:
        cur = conn.execute('DELETE FROM jobs WHERE id=?', (job_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_all_jobs() -> int:
    conn = _db()
    try:
        cur = conn.execute('DELETE FROM jobs')
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
