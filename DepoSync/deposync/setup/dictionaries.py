# -*- coding: utf-8 -*-
"""
Legal / medical lexicon for DepoSync.

Two jobs (per user request):
  1. Improve speech recognition of legal/medical terms & proper nouns during
     sync, by feeding a domain vocabulary to Whisper as an initial prompt.
  2. Spell-check / normalize exhibit and party names (closest-match cleanup).

A small bundled base list ships with the app. The first-run setup can drop
extended word lists into <install>/dict/*.txt (one term per line); those are
merged on load so the vocabulary grows without code changes.
"""
import re
import difflib
from functools import lru_cache

# Compact, high-value base vocabulary. Extended lists live in <install>/dict.
_BASE_LEGAL = [
    'deposition', 'deponent', 'plaintiff', 'defendant', 'counsel', 'objection',
    'foundation', 'hearsay', 'stipulate', 'stipulation', 'privilege',
    'privileged', 'subpoena', 'affidavit', 'interrogatory', 'interrogatories',
    'exhibit', 'errata', 'videographer', 'stenographer', 'certify', 'certified',
    'verbatim', 'examination', 'cross-examination', 'redirect', 'voir', 'dire',
    'testimony', 'testify', 'witness', 'oath', 'perjury', 'transcript',
    'litigation', 'plaintiffs', 'defendants', 'whereof', 'aforementioned',
    'notary', 'jurisdiction', 'allegation', 'allegations', 'damages',
    'negligence', 'liability', 'plaintiff\u2019s', 'defendant\u2019s',
]
_BASE_MEDICAL = [
    'diagnosis', 'prognosis', 'etiology', 'idiopathic', 'comorbidity',
    'myocardial', 'infarction', 'ischemia', 'hypertension', 'hypotension',
    'tachycardia', 'bradycardia', 'edema', 'hematoma', 'contusion',
    'laceration', 'fracture', 'lumbar', 'cervical', 'thoracic', 'vertebra',
    'radiculopathy', 'herniation', 'orthopedic', 'neurological', 'analgesic',
    'anesthesia', 'anesthesiologist', 'prescription', 'dosage', 'milligram',
    'radiograph', 'magnetic', 'resonance', 'imaging', 'palpation',
]


@lru_cache(maxsize=1)
def _terms() -> tuple:
    """Bundled base + any extended lists found in the install dict dir."""
    terms = set(t.lower() for t in (_BASE_LEGAL + _BASE_MEDICAL))
    try:
        from deposync.config import CONFIG
        for f in CONFIG.dict_dir.glob('*.txt'):
            try:
                for line in f.read_text('utf-8', errors='replace').splitlines():
                    w = line.strip().lower()
                    if w and not w.startswith('#'):
                        terms.add(w)
            except Exception:
                continue
    except Exception:
        pass
    return tuple(sorted(terms))


def reload_terms():
    _terms.cache_clear()


def whisper_prompt(extra_names=None, max_terms: int = 220) -> str:
    """
    Build an initial_prompt string biasing Whisper toward legal/medical
    vocabulary and case-specific proper nouns (party/witness names).
    """
    terms = list(_terms())[:max_terms]
    names = [n for n in (extra_names or []) if n]
    vocab = ', '.join(names + terms)
    return ('This is a legal deposition transcript. Expect legal and medical '
            'terminology and proper names such as: ' + vocab + '.')


def normalize_name(name: str) -> str:
    """
    Tidy a party / witness / exhibit name: collapse whitespace, fix casing,
    and snap obvious misspellings of known terms to the lexicon.
    """
    if not name:
        return ''
    name = re.sub(r'\s+', ' ', name).strip()
    out = []
    terms = _terms()
    for tok in name.split(' '):
        core = re.sub(r'[^A-Za-z\u2019\'-]', '', tok)
        if len(core) >= 5 and core.lower() not in terms:
            match = difflib.get_close_matches(core.lower(), terms, n=1, cutoff=0.88)
            if match:
                fixed = match[0]
                core = fixed.capitalize() if core[0].isupper() else fixed
                tok = tok.replace(re.sub(r'[^A-Za-z\u2019\'-]', '', tok), core)
        out.append(tok)
    cleaned = ' '.join(out)
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()
    return cleaned
