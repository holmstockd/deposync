# -*- coding: utf-8 -*-
"""
Page-image / E-Transcript ASCII parser.

Real deposition ASCII (E-Transcript, LiveNote print image, etc.) is a *page
image*: pages are separated by form-feed (\\x0c), each page prints up to N
numbered lines (line number right-aligned in a fixed left column), lines are
often double-spaced, and text may wrap onto un-numbered continuation lines.

This parser reproduces that exact physical layout -- one `Line` per printed
line -- which is what TimeCoder/Sanction (.mdb/.cms) and TextMap (.ptf/.xmef)
store and what lawyers cite (page:line). It is far more accurate for these
files than the generic indented parser.
"""
import re
from typing import List
from deposync.models import Line

# A numbered transcript line: a small left margin, a 1-2 digit line number,
# then (optionally) >=1 spaces and the text. Empty numbered lines are allowed.
_NUM = re.compile(r'^ {1,15}(\d{1,2})(?: +(.*))?$')


def looks_like_page_image(raw: str) -> bool:
    """Heuristic: form-feeds present, or many right-margin numbered lines."""
    if '\f' in raw:
        return True
    sample = raw.splitlines()[:400]
    hits = sum(1 for ln in sample if _NUM.match(ln))
    return hits >= 20


def parse_pages(path: str, raw: str = None) -> List[Line]:
    """Parse a page-image transcript into physical `Line`s (incl. continuations)."""
    if raw is None:
        raw = _read(path)
    # Split into pages on form-feed; if none, treat the whole doc as one page
    # and let line-number resets define page boundaries.
    chunks = raw.split('\f') if '\f' in raw else _split_by_linereset(raw)

    out: List[Line] = []
    for pageno, chunk in enumerate(chunks, 1):
        cur_ln = 0
        seen_number = False
        for physical in chunk.split('\n'):
            if not physical.strip():
                continue                      # skip blank (double-spacing)
            m = _NUM.match(physical)
            if m:
                cur_ln = int(m.group(1))
                body = (m.group(2) or '').rstrip()
                out.append(Line(page=pageno, line_num=cur_ln, text=body,
                                raw=physical.rstrip(), is_cont=False))
                seen_number = True
            else:
                # continuation / caption / header / footer
                stripped = physical.strip()
                if not seen_number:
                    continue                  # page header before line 1
                if stripped.isdigit():
                    continue                  # standalone page-number footer
                out.append(Line(page=pageno, line_num=cur_ln, text=stripped,
                                raw=physical.rstrip(), is_cont=True))
    return out


def _split_by_linereset(raw: str) -> List[str]:
    """Fallback page split when there are no form-feeds: start a new page each
    time the line number sequence drops back toward 1."""
    pages, cur, last = [], [], 0
    for ln in raw.split('\n'):
        m = _NUM.match(ln)
        if m:
            n = int(m.group(1))
            if n <= last and n <= 2 and cur:
                pages.append('\n'.join(cur)); cur = []
            last = n
        cur.append(ln)
    if cur:
        pages.append('\n'.join(cur))
    return pages or [raw]


def _read(path: str) -> str:
    from pathlib import Path
    return Path(path).read_text(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Display helpers -- reproduce the printed text for exporters.
# ---------------------------------------------------------------------------

def detect_margin(lines: List[Line]) -> int:
    """Smallest left indent among numbered raw lines = the number column start."""
    indents = []
    for l in lines:
        if not l.is_cont and l.raw:
            indents.append(len(l.raw) - len(l.raw.lstrip(' ')))
    return min(indents) if indents else 0


def mdb_display(line: Line, margin: int) -> str:
    """Sanction/MDB display text -- KEEPS the line number (e.g. ' 5   THE...')."""
    s = (line.raw[margin:] if line.raw else line.text).rstrip()
    return s


def ptf_display(line: Line, margin: int) -> str:
    """TextMap/PTF display text -- line number blanked out, spacing preserved."""
    s = (line.raw[margin:] if line.raw else line.text).rstrip()
    if not line.is_cont:
        # Blank the leading line-number token (keep column alignment).
        m = re.match(r'^(\s*)(\d{1,2})(.*)$', s)
        if m:
            s = m.group(1) + (' ' * len(m.group(2))) + m.group(3)
    return s
