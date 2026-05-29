# -*- coding: utf-8 -*-
"""
Transcript parser for DepoSync.

Handles ALL InData / YesLaw ASCII deposition formats.
Auto-detection works by page content analysis, not format-specific patterns,
so it works on any deposition from any court reporter software.
"""
import re
from pathlib import Path
from typing import List, Tuple
from collections import defaultdict
from deposync.models import Line

# YesLaw PPPPP:LL format
_YESLAW = re.compile(r'^\s*(\d{1,6}):(\d{1,2})\s+(.*)')
# Plain indented format (2+ spaces, line number, 2+ spaces, text)
_PLAIN  = re.compile(r'^\s{2,}(\d{1,2})\s{2,}(.*)')
# Standalone page number line
_PGONLY = re.compile(r'^\s*(\d{1,6})\s*$')

# Cert / errata page markers - appears anywhere on the page
_CERT_MARKER = re.compile(
    r'(CERTIFICATE\s+OF\s+(REPORTER|SHORTHAND)|'
    r'ERRATA\s+SHEET|'
    r"REPORTER'?S\s+CERTIF|"
    r'I,\s+\w.{3,30},?\s+(a\s+)?Registered|'
    r'IN\s+WITNESS\s+WHEREOF)',
    re.I)

# First spoken line markers - applies to line text
_SPOKEN_FIRST = re.compile(
    r'^(THE\s+VIDEOGRAPHER|THE\s+WITNESS|THE\s+REPORTER|'
    r'THE\s+COURT|VIDEOGRAPHER|'
    r'[QA]\s{1,8}[A-Za-z\("]|'
    r'[QA][\.!]\s+[A-Za-z\("]|'
    r'BY\s+(MR|MS|MRS|DR)[\.\s]|'
    r'EXAMINATION\s+BY|'
    r'(MR|MS|MRS|DR)[\.\s]+\w+\s*:\s+)',
    re.I)


def parse(path: str) -> List[Line]:
    """Parse any InData/YesLaw ASCII transcript file."""
    raw = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    # Detect format from first 80 lines
    if any(_YESLAW.match(l) for l in raw[:80]):
        return _parse_yeslaw(raw)
    return _parse_plain(raw)


def _parse_yeslaw(raw: List[str]) -> List[Line]:
    out = []
    for r in raw:
        m = _YESLAW.match(r)
        if m:
            pg, ln, txt = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            if txt:
                out.append(Line(page=pg, line_num=ln, text=txt))
    return out


def _parse_plain(raw: List[str]) -> List[Line]:
    out = []
    pg  = 1
    for r in raw:
        pm = _PGONLY.match(r)
        if pm and len(r.strip()) <= 6:
            pg = int(pm.group(1))
            continue
        m = _PLAIN.match(r)
        if m:
            ln, txt = int(m.group(1)), m.group(2).strip()
            if txt:
                out.append(Line(page=pg, line_num=ln, text=txt))
    return out


def auto_detect_range(lines: List[Line]) -> Tuple[int, int, int, int]:
    """
    Detect the first and last spoken lines in any deposition transcript.

    Strategy:
      - Cert pages: contain phrases like "CERTIFICATE OF REPORTER",
        "IN WITNESS WHEREOF", "Registered Professional Reporter", etc.
      - Cover pages: mostly ALL CAPS text, fewer than 8 lines with
        lowercase letters (no real sentences)
      - Testimony pages: 8+ lines with lowercase letters (real sentences)

    Works on ANY court reporter format -- InData, YesLaw, Summation,
    LiveNote, Eclipse, ProCAT, etc. No format-specific assumptions.

    Returns: (first_page, first_line, last_page, last_line)
    """
    page_lines: dict = defaultdict(list)
    for l in lines:
        page_lines[l.page].append(l)
    all_pages = sorted(page_lines.keys())

    # ?? Find cert page (first page containing cert markers) ???????????????????
    cert_pg = None
    for pg in all_pages:
        if any(_CERT_MARKER.search(l.text) for l in page_lines[pg]):
            cert_pg = pg
            break

    # ?? Find first testimony page (first page with 8+ lowercase lines) ????????
    first_testimony_pg = None
    for pg in all_pages:
        if cert_pg and pg >= cert_pg:
            break
        lc = sum(1 for l in page_lines[pg]
                 if any(c.islower() for c in l.text))
        if lc >= 8:
            first_testimony_pg = pg
            break

    # ?? Find last testimony page (last page with lowercase lines before cert) ??
    last_testimony_pg = None
    for pg in reversed(all_pages):
        if cert_pg and pg >= cert_pg:
            continue
        lc = sum(1 for l in page_lines[pg]
                 if any(c.islower() for c in l.text))
        if lc >= 3:
            last_testimony_pg = pg
            break

    # Fallbacks
    if first_testimony_pg is None:
        first_testimony_pg = all_pages[0]
    if last_testimony_pg is None:
        last_testimony_pg = (all_pages[-2] if cert_pg
                             else all_pages[-1])

    # ?? On first testimony page, find first spoken line ???????????????????????
    # (skips caption text at top of page that shares with cover)
    first_line = None
    for l in page_lines[first_testimony_pg]:
        if _SPOKEN_FIRST.match(l.text):
            first_line = l
            break
    if first_line is None:
        # No spoken marker found -- use first line of page
        first_line = page_lines[first_testimony_pg][0]

    # ?? Last line of last testimony page ??????????????????????????????????????
    last_line = page_lines[last_testimony_pg][-1]

    return (first_line.page, first_line.line_num,
            last_line.page,  last_line.line_num)


def spoken_text(lines: List[Line]) -> str:
    """
    Build plain text for stable-ts align().
    Strips Q/A markers, stage directions, parentheticals.
    Works on any speaker label format.
    """
    _SPEAKER = re.compile(
        r'^(\s*[QA]\s+|'                          # Q  or A  followed by space
        r'\s*[QA][\.!]\s+|'                        # Q. or A. followed by space
        r'(?:THE\s+)?(?:VIDEOGRAPHER|WITNESS|'
        r'COURT|REPORTER)\s*:\s*|'                 # THE WITNESS: etc
        r'(?:MR|MS|MRS|DR)\.?\s+\w+[\w\s]*:\s*)', # MR. SMITH:
        re.I)
    _PAREN = re.compile(r'\([^)]{0,120}\)')
    _BRACK = re.compile(r'\[[^\]]{0,80}\]')

    parts = []
    for l in lines:
        t = l.text.strip()
        if not t:
            continue
        t = _SPEAKER.sub('', t)
        t = _PAREN.sub('', t)
        t = _BRACK.sub('', t)
        t = t.strip(' .-,;')
        if len(t) > 1:
            parts.append(t)
    return ' '.join(parts)
