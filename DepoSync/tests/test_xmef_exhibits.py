# -*- coding: utf-8 -*-
"""Regression tests for XMEF export with linked exhibits."""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deposync.models import Line, Exhibit          # noqa: E402
from deposync.export.xmef_export import write       # noqa: E402


def _lines():
    return [
        Line(1, 1, "Q. Please look at Exhibit 5.", timestamp_sec=10.0),
        Line(1, 2, "A. I see it.", timestamp_sec=12.5),
        Line(2, 1, "Q. And Exhibit 12?", timestamp_sec=20.0),
    ]


def test_xmef_no_exhibits_still_writes():
    out = tempfile.mktemp(suffix=".xmef")
    n = write(_lines(), out, witness="Test")
    assert n == 3
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert any(x.endswith(".ptf") for x in names)
        assert "XMEFManifest.xml" in names


def test_xmef_bundles_linked_exhibits():
    ex_file = tempfile.mktemp(suffix=".pdf")
    with open(ex_file, "wb") as f:
        f.write(b"%PDF-1.4 fake")
    exhibits = [Exhibit(label="Exhibit 5", number="5", page=1, line_num=1,
                        ref_count=1, file_path=ex_file)]
    out = tempfile.mktemp(suffix=".xmef")
    write(_lines(), out, witness="Test", exhibits=exhibits)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert any(x.startswith("Exhibits/") for x in names)
        ptf = zf.read([x for x in names if x.endswith(".ptf")][0]).decode("utf-8")
        assert "begin=Annotation" in ptf
        assert "Exhibit 5" in ptf
        assert "link=Exhibits/" in ptf
