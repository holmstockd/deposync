# -*- coding: utf-8 -*-
"""
Exhibit reference detection + file linking.

Scans a parsed transcript for exhibit references such as:
    "Exhibit 5", "Exhibit No. 12", "Plaintiff's Exhibit A",
    "Defendant's Exhibit 3", "Deposition Exhibit 7", "Depo. Ex. 4",
    "Joint Exhibit 2", "Government Exhibit 9"
and links imported exhibit files to the page:line where each is FIRST mentioned.
Nothing is preset -- exhibit numbers/pages are detected per transcript.
"""
import os
import re
from typing import List, Dict
from dataclasses import dataclass

from deposync.models import Line, Exhibit

# party / kind qualifier that may precede "Exhibit"
_QUAL = (r"(?:Plaintiff'?s?|Defendant'?s?|Deposition|Depo\.?|Joint|"
         r"Government|State'?s?|Petitioner'?s?|Respondent'?s?|Defense)")
# number can be digits or short letter runs (A, AB) optionally with suffix
_NUM = r"(\d{1,4}[A-Za-z]?|[A-Z]{1,3})"

_EXHIBIT_RE = re.compile(
    rf"(?:({_QUAL})\s+)?"
    rf"(?:Exhibit|Exh\.?|Ex\.?)\s+(?:No\.?\s*|Number\s+|#\s*)?"
    rf"({_NUM})\b",
    re.IGNORECASE)


@dataclass
class ExhibitRef:
    qualifier: str
    number:    str
    page:      int
    line_num:  int
    raw:       str

    @property
    def label(self) -> str:
        q = (self.qualifier or '').strip()
        if q:
            q = q[0].upper() + q[1:]
            return f'{q} Exhibit {self.number}'
        return f'Exhibit {self.number}'

    @property
    def key(self) -> str:
        # match key ignores qualifier; exhibit numbers are case-insensitive
        return str(self.number).upper().lstrip('0') or '0'


def find_exhibit_refs(lines: List[Line]) -> List[ExhibitRef]:
    """All exhibit references found, in document order."""
    refs: List[ExhibitRef] = []
    for l in lines:
        for m in _EXHIBIT_RE.finditer(l.text):
            qual, num = m.group(1), m.group(2)
            if not _valid_exhibit_number(num):
                continue
            refs.append(ExhibitRef(qualifier=qual or '', number=num,
                                   page=l.page, line_num=l.line_num,
                                   raw=m.group(0)))
    return refs


def _valid_exhibit_number(num: str) -> bool:
    """Reject prose false-positives ('Ex. it/and/is'). Accept '5', '22A', 'A'.

    Letter exhibits must be 1-2 UPPERCASE letters (case-sensitive) so that
    case-insensitive keyword matching does not swallow ordinary words.
    """
    if re.fullmatch(r'\d{1,4}[A-Z]?', num):       # 5, 12, 22A
        return True
    if re.fullmatch(r'[A-Z]{1,2}', num):          # A, B, AB
        return True
    return False


def unique_exhibits(refs: List[ExhibitRef]) -> List[Exhibit]:
    """
    Collapse references to one Exhibit per number, recording the FIRST
    citation page:line and how many times it is referenced.
    """
    by_key: Dict[str, Exhibit] = {}
    for r in refs:
        ex = by_key.get(r.key)
        if ex is None:
            by_key[r.key] = Exhibit(
                label=r.label, number=str(r.number),
                page=r.page, line_num=r.line_num, ref_count=1)
        else:
            ex.ref_count += 1
            if (r.page, r.line_num) < (ex.page, ex.line_num):
                ex.page, ex.line_num, ex.label = r.page, r.line_num, r.label
    return sorted(by_key.values(),
                  key=lambda e: (e.page or 0, e.line_num or 0))


def _number_from_filename(path: str) -> str:
    """Pull an exhibit number/letter from a filename for auto-matching."""
    base = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r'(?:exhibit|exh|ex)[ _\-#]*([0-9]{1,4}[a-zA-Z]?|[A-Za-z]{1,3})',
                  base, re.IGNORECASE)
    if m:
        return m.group(1).upper().lstrip('0') or '0'
    m = re.search(r'\b([0-9]{1,4})\b', base)
    return (m.group(1).lstrip('0') or '0') if m else ''


def link_files(lines: List[Line], file_paths: List[str]) -> List[Exhibit]:
    """
    Build the exhibit list from the transcript, then attach each imported
    file to the matching exhibit number (by filename). Unmatched files are
    appended as exhibits with no citation so the user can fix them.
    """
    refs = find_exhibit_refs(lines)
    exhibits = unique_exhibits(refs)
    by_key = {e.number.upper().lstrip('0') or '0': e for e in exhibits}

    used = set()
    for p in file_paths:
        k = _number_from_filename(p)
        ex = by_key.get(k)
        if ex and not ex.file_path:
            ex.file_path = p
            used.add(p)
    for p in file_paths:
        if p not in used:
            num = _number_from_filename(p) or '?'
            exhibits.append(Exhibit(
                label=f'Exhibit {num}', number=num, file_path=p,
                description='auto-import: no transcript reference found'))
    return exhibits
