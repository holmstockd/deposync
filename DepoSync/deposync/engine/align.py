# -*- coding: utf-8 -*-
"""
DepoSync alignment engine.

stable-ts forced alignment + iterative (non-recursive) mapping.

The RecursionError in previous builds was caused by nested loops
searching backward/forward for anchors across 4000+ lines.
This version is fully iterative - no function calls in loops.
"""
import sys
import re
import subprocess
from typing import List, Optional, Callable, Tuple

from deposync.models import Line, Word

# Raise Python's recursion limit and use iterative algorithms
sys.setrecursionlimit(10000)


# ?????????????????????????????????????????????????????????????????????????????
# GPU detection
# ?????????????????????????????????????????????????????????????????????????????

def detect_device() -> Tuple[str, str, str]:
    """
    Return (device, compute_type, description).
    Checks NVIDIA CUDA first, then AMD ROCm, then CPU.
    AMD ROCm on Windows needs the ROCm PyTorch wheel:
      pip install torch --index-url https://download.pytorch.org/whl/rocm6.2
    """
    # NVIDIA CUDA
    try:
        import torch
        if torch.cuda.is_available():
            hip = getattr(torch.version, 'hip', None)
            if not hip:
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory // (1024**3)
                maj  = torch.cuda.get_device_properties(0).major
                ctype = 'float16' if maj >= 7 else 'int8_float16'
                return 'cuda', ctype, f'NVIDIA {name} ({vram}GB)'
    except Exception:
        pass

    # AMD ROCm (presents as cuda when ROCm wheel installed)
    try:
        import torch
        hip = getattr(torch.version, 'hip', None)
        if hip and torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024**3)
            return 'cuda', 'float16', f'AMD ROCm {name} ({vram}GB)'
    except Exception:
        pass

    # Detect GPU vendor for helpful install message
    vendor, gpu_name = _gpu_vendor_windows()

    if vendor == 'NVIDIA':
        desc = (f'CPU  [NVIDIA GPU detected: {gpu_name} -- '
                f'run INSTALL.bat to enable CUDA]')
    elif vendor == 'AMD':
        desc = (f'CPU  [AMD GPU detected: {gpu_name}. The Whisper engine '
                f'(faster-whisper / CTranslate2) supports NVIDIA CUDA or CPU '
                f'only -- AMD GPUs are not supported, so CPU is normal and '
                f'expected here.]')
    else:
        try:
            import psutil
            cores = psutil.cpu_count(logical=False) or 4
            desc  = f'CPU ({cores} cores)'
        except Exception:
            desc = 'CPU'

    return 'cpu', 'int8', desc


def _gpu_vendor_windows() -> Tuple[str, str]:
    """Detect GPU vendor via nvidia-smi, rocm-smi, or PowerShell WMI."""
    # nvidia-smi
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return 'NVIDIA', r.stdout.strip().split('\n')[0]
    except Exception:
        pass

    # PowerShell WMI - checks AdapterCompatibility for "Advanced Micro Devices"
    try:
        r = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-WmiObject Win32_VideoController | '
             'Select-Object Name,AdapterCompatibility | ConvertTo-Json'],
            capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip():
            import json
            raw = r.stdout.strip()
            if not raw.startswith('['):
                raw = f'[{raw}]'
            for adapter in json.loads(raw):
                name   = (adapter.get('Name') or '').strip()
                compat = (adapter.get('AdapterCompatibility') or '').strip()
                if ('Advanced Micro Devices' in compat or
                        'AMD' in compat.upper() or
                        'AMD' in name.upper() or
                        'RADEON' in name.upper()):
                    return 'AMD', name
                if 'NVIDIA' in compat.upper() or 'NVIDIA' in name.upper():
                    return 'NVIDIA', name
    except Exception:
        pass

    return '', ''


# ?????????????????????????????????????????????????????????????????????????????
# Model cache
# ?????????????????????????????????????????????????????????????????????????????

_cache: dict = {}


def _load_model(model_size: str, device: str, compute_type: str):
    key = (model_size, device, compute_type)
    if key not in _cache:
        import stable_whisper
        _cache[key] = stable_whisper.load_faster_whisper(
            model_size, device=device, compute_type=compute_type)
    return _cache[key]


# ?????????????????????????????????????????????????????????????????????????????
# Main entry point
# ?????????????????????????????????????????????????????????????????????????????

def run(
    audio_path: str,
    lines:      List[Line],
    model_size: str = 'base.en',
    language:   str = 'en',
    offset_sec: float = 0.0,
    progress:   Optional[Callable[[int, str], None]] = None,
) -> List[Line]:
    """
    Force-align lines to audio using stable-ts DTW.
    Returns lines with timestamp_sec and confidence filled in.
    Fully iterative - no recursion.
    """
    cb = progress or (lambda p, m: None)

    device, compute_type, hw_desc = detect_device()
    cb(0, f'Engine: stable-ts forced alignment | {hw_desc}')

    # Build transcript text for stable-ts
    from deposync.parser.transcript import spoken_text as build_text
    text = build_text(lines)
    if not text.strip():
        raise ValueError('Transcript text is empty after cleaning.')

    word_count = len(text.split())
    cb(2, f'Aligning {word_count} transcript words on {device.upper()}...')

    # Load model
    model = _load_model(model_size, device, compute_type)

    # Get audio duration for progress estimation
    try:
        import soundfile as sf
        with sf.SoundFile(audio_path) as af:
            audio_dur_secs = len(af) / af.samplerate
    except Exception:
        audio_dur_secs = 0.0

    # stable-ts align() is synchronous with no callbacks.
    # Run a timer thread to pulse progress based on elapsed time vs expected duration.
    # CPU: ~4 min/hr of audio.  GPU (CUDA): ~1 min/hr.
    import threading, time as _time
    _stop_pulse = threading.Event()

    def _progress_pulse():
        expected_secs = (audio_dur_secs / 3600.0) * (240 if device == 'cpu' else 60)
        if expected_secs < 10:
            expected_secs = 300  # fallback if duration unknown
        t0 = _time.time()
        while not _stop_pulse.is_set():
            elapsed = _time.time() - t0
            pct = min(int(elapsed / expected_secs * 68) + 2, 70)
            mins_left = max(0, int((expected_secs - elapsed) / 60))
            secs_left = max(0, int((expected_secs - elapsed) % 60))
            dur_msg = f'{audio_dur_secs/60:.0f}min audio' if audio_dur_secs else 'audio'
            cb(pct,
               f'Forced alignment running on {device.upper()}  |  '
               f'{dur_msg}  |  '
               f'~{mins_left}:{secs_left:02d} remaining  |  '
               f'Elapsed {int(elapsed//60)}:{int(elapsed%60):02d}')
            _stop_pulse.wait(timeout=3.0)

    pulse_thread = threading.Thread(target=_progress_pulse, daemon=True)
    pulse_thread.start()

    # Run forced alignment
    try:
        result = model.align(
            audio_path, text, language=language, verbose=None)
    except Exception as e:
        raise RuntimeError(f'stable-ts align() failed: {e}')
    finally:
        _stop_pulse.set()
        pulse_thread.join(timeout=2)

    if result is None:
        raise RuntimeError('stable-ts returned no result.')

    # Extract word timestamps - fully iterative, no recursion
    cb(75, 'Extracting word timestamps...')
    words: List[Word] = _extract_words(result, offset_sec)

    if not words:
        raise RuntimeError(
            'stable-ts produced no word timestamps. '
            'Check that the audio is audible and the transcript matches.')

    cb(80, f'Got {len(words)} word timestamps. Mapping to lines...')

    # Map words to lines - iterative forward sweep
    _map_words_to_lines(lines, words, cb)

    # Interpolate gaps - iterative two-pass
    cb(96, 'Interpolating gaps...')
    _interpolate_iterative(lines)

    matched  = sum(1 for l in lines if l.timestamp_sec is not None)
    pct      = int(matched * 100 / max(len(lines), 1))
    cb(100, f'Done: {matched}/{len(lines)} lines timestamped ({pct}%).')
    return lines


def _extract_words(result, offset_sec: float) -> List[Word]:
    """Extract word list from stable-ts result. Handles None segments safely."""
    words = []
    try:
        for seg in (result.segments or []):
            if seg is None:
                continue
            for w in (seg.words or []):
                if w is None:
                    continue
                text  = getattr(w, 'word', '') or ''
                start = float(getattr(w, 'start', 0.0) or 0.0) + offset_sec
                end   = float(getattr(w, 'end', start) or start) + offset_sec
                if text.strip():
                    words.append(Word(text=text,
                                      start=round(start, 3),
                                      end=round(end, 3)))
    except Exception:
        pass
    return words


# ?????????????????????????????????????????????????????????????????????????????
# Word-to-line mapping  (iterative, O(n) forward sweep)
# ?????????????????????????????????????????????????????????????????????????????

_CLEAN_RE = re.compile(r'[^a-z0-9]')


def _norm(s: str) -> str:
    return _CLEAN_RE.sub('', s.lower())


def _map_words_to_lines(
    lines: List[Line],
    words: List[Word],
    cb:    Callable,
) -> None:
    """
    Walk transcript lines and word list together in one forward pass.
    For each line find its first content word in words[cursor:cursor+WIN].
    cursor only moves forward - O(n) total.
    """
    if not words:
        return

    n_words = len(words)
    total   = words[-1].end
    wps     = n_words / max(total, 1)
    WIN     = max(20, int(30 * wps))    # 30-second window

    # Pre-normalize all words once
    wn = [_norm(w.text) for w in words]

    cursor  = 0
    n_lines = len(lines)

    for i, line in enumerate(lines):
        if i % 500 == 0:
            matched_so_far = sum(1 for l in lines[:i] if l.timestamp_sec is not None)
            cb(80 + int(i / max(n_lines, 1) * 15),
               f'Mapping line {i}/{n_lines}  matched={matched_so_far}')

        if line.manually_set or not line.text.strip():
            continue

        # Get content tokens from transcript line (length >= 4, not stopwords)
        raw_toks = re.findall(r'[a-zA-Z]+', line.text)
        toks = [_norm(t) for t in raw_toks if len(t) >= 4]
        if not toks:
            continue

        # Search for each token in window, take first match
        best_wi = -1
        end_wi  = min(n_words, cursor + WIN)

        for tok in toks:
            if best_wi >= 0:
                break
            tok4 = tok[:4]
            for wi in range(cursor, end_wi):
                w = wn[wi]
                if w == tok or (len(w) >= 4 and w[:4] == tok4):
                    best_wi = wi
                    break

        if best_wi >= 0:
            line.timestamp_sec = words[best_wi].start
            line.confidence    = 0.99   # direct DTW match -> GREEN
            cursor = best_wi + 1


# ?????????????????????????????????????????????????????????????????????????????
# Gap interpolation  (fully iterative, no recursion)
# ?????????????????????????????????????????????????????????????????????????????

def _interpolate_iterative(lines: List[Line]) -> None:
    """
    Fill every unmatched line with a timestamp interpolated between
    its nearest confirmed neighbors. Two linear passes, no function calls.
    """
    n = len(lines)

    # Pass A: build prev_ts[i] = timestamp of nearest preceding matched line
    prev_ts   = [None] * n
    prev_idx  = [None] * n
    last_ts   = None
    last_i    = None
    for i in range(n):
        if lines[i].timestamp_sec is not None:
            last_ts = lines[i].timestamp_sec
            last_i  = i
        prev_ts[i]  = last_ts
        prev_idx[i] = last_i

    # Pass B: build next_ts[i] = timestamp of nearest following matched line
    next_ts  = [None] * n
    next_idx = [None] * n
    nxt_ts   = None
    nxt_i    = None
    for i in range(n - 1, -1, -1):
        if lines[i].timestamp_sec is not None:
            nxt_ts = lines[i].timestamp_sec
            nxt_i  = i
        next_ts[i]  = nxt_ts
        next_idx[i] = nxt_i

    # Pass C: fill gaps
    for i in range(n):
        line = lines[i]
        if line.timestamp_sec is not None or line.manually_set:
            continue
        if not line.text.strip():
            continue

        pt = prev_ts[i]
        nt = next_ts[i]
        pi = prev_idx[i]
        ni = next_idx[i]

        if pt is not None and nt is not None and nt > pt and ni > pi:
            # Linear interpolation between confirmed anchors
            frac = (i - pi) / (ni - pi)
            line.timestamp_sec = round(pt + frac * (nt - pt), 3)
            # Confidence based on gap size
            gap_lines = ni - pi
            line.confidence = 0.85 if gap_lines <= 3 else \
                              0.75 if gap_lines <= 10 else \
                              0.70
        elif pt is not None:
            # After last anchor, use last known time
            line.timestamp_sec = pt
            line.confidence    = 0.70
