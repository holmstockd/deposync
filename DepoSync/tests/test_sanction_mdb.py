# -*- coding: utf-8 -*-
"""Regression tests for the Sanction/OnCue MDB row-building logic.

These cover the cross-platform (pure-Python) parts of sanction_mdb. The actual
Jet/Access file write is Windows-only (pywin32) and is not exercised here.

Run:  python -m pytest DepoSync/tests -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deposync.models import Line                       # noqa: E402
from deposync.export import sanction_mdb as s          # noqa: E402


def _lines():
    return [
        Line(1, 1, "UNITED STATES DISTRICT COURT"),
        Line(1, 2, "SOUTHERN DISTRICT OF NEW YORK"),
        Line(9, 5, "THE VIDEOGRAPHER: This begins", timestamp_sec=7.299),
        Line(9, 6, "the video recorded deposition of", timestamp_sec=9.823),
    ]


def test_timestamp_truncates_not_rounds():
    # sample files truncate: 9.823 -> 00:00:09 (not 00:00:10)
    assert s._hms(9.823) == "00:00:09"
    assert s._hms(7.299) == "00:00:07"
    assert s._hms(3661) == "01:01:01"
    assert s._hms(None) == ""


def test_name_split():
    assert s.split_name("Starr, Alexander 3.31.2026") == {
        "first": "Alexander", "last": "Starr"}
    assert s.split_name("Alexander Starr") == {
        "first": "Alexander", "last": "Starr"}


def test_main_rows_have_page_markers_and_continuous_index():
    rows = s.build_main_rows(_lines())
    # one PG marker per distinct page (pages 1 and 9) + 4 LN rows = 6
    pg = [r for r in rows if r["Temp"] == "PG"]
    ln = [r for r in rows if r["Temp"] == "LN"]
    assert len(pg) == 2 and len(ln) == 4
    assert [r["Index"] for r in rows] == list(range(1, len(rows) + 1))
    assert pg[0]["Text"] == "Page 1" and pg[0]["LineNum"] == 0


def test_synced_vs_unsynced_timecode():
    rows = s.build_main_rows(_lines())
    synced = [r for r in rows if r["Temp"] == "LN" and r["Timecode"] is not None]
    assert len(synced) == 2
    assert synced[0]["Timecode"] == 7.299
    assert synced[0]["TimeStamp"] == "00:00:07"


def test_build_tables_info_and_mpegs():
    t = s.build_tables(_lines(), witness="Starr, Alexander 3.31.2026",
                       video_path="C:/Media/AS033126.mpg",
                       video_dur_sec=13076.995)
    info = t["Info"][0]
    assert info["FirstName"] == "Alexander" and info["LastName"] == "Starr"
    assert info["StartPage"] == 1 and info["EndPage"] == 9
    assert info["LinesPerPage"] == 25 and info["Complete"] is True
    mp = t["MPEGS"][0]
    assert mp["ID"] == "AS033126" and mp["Duration"] == 13076.995
    assert mp["Offset"] == 0.0


def test_text_truncated_to_120():
    rows = s.build_main_rows([Line(1, 1, "x" * 200)])
    ln = [r for r in rows if r["Temp"] == "LN"][0]
    assert len(ln["Text"]) == 120
