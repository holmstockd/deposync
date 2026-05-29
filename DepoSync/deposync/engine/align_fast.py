# -*- coding: utf-8 -*-
"""
Fast waveform-based alignment (the default sync engine).

This does NOT use AI speech recognition. Like InData TimeCoder Pro / YesLaw,
it works directly from the audio waveform:

  1. Voice-activity detection (energy based) finds where speech occurs and
     excludes silence, breaks, recesses and off-record gaps.
  2. The transcript lines are distributed across the *speech* timeline,
     weighted by how much is spoken on each line (character count of the
     cleaned text).

Because silence does not advance the "speech clock", recesses and pauses are
handled automatically, so timings track real speech across multi-hour jobs.

Speed: a few seconds for hours of audio (vs. ~15-30 min for Whisper on CPU),
and it is completely GPU-independent. Results are approximate (good for
navigation); the user refines hot spots with TAP SYNC.

General: no per-job tuning -- thresholds are derived from each file's own
energy distribution, so it works on any deposition recording.
"""
from typing import List, Optional, Callable

import numpy as np

from deposync.models import Line
from deposync.parser.transcript import spoken_text as _spoken

SR_TARGET = 16000
FRAME = 512                     # 32 ms analysis frame @ 16 kHz
FRAME_SEC = FRAME / SR_TARGET


def _frame_energy(path: str, progress: Callable[[int, str], None]):
    """Stream the audio and return (rms_per_frame, samplerate). Low memory."""
    block = FRAME * 4000        # ~128 s per read
    carry = np.empty(0, dtype="float32")
    chunks = []
    sr = SR_TARGET
    read = 0
    with __import__("soundfile").SoundFile(path) as f:
        sr = f.samplerate
        total = max(len(f), 1)
        while True:
            data = f.read(block, dtype="float32")
            if len(data) == 0:
                break
            if getattr(data, "ndim", 1) > 1:
                data = data.mean(axis=1)
            read += len(data)
            data = np.concatenate([carry, data]) if carry.size else data
            n = len(data) // FRAME
            carry = data[n * FRAME:]
            if n:
                fr = data[:n * FRAME].reshape(n, FRAME)
                chunks.append(np.sqrt((fr * fr).mean(axis=1)))
            progress(min(40, int(read / total * 40)),
                     f"Scanning audio waveform... {int(read/sr/60)} min")
    energy = np.concatenate(chunks) if chunks else np.array([], dtype="float32")
    return energy, sr


def _speech_mask(energy: np.ndarray) -> np.ndarray:
    """Adaptive speech/silence classification from the file's own energy."""
    if energy.size == 0:
        return energy.astype(bool)
    es = np.sort(energy)
    k = max(1, energy.size // 5)
    noise = float(es[:k].mean())              # quietest 20% ~ silence
    loud = float(es[-k:].mean())              # loudest 20% ~ speech
    thresh = noise + 0.06 * (loud - noise)    # low threshold = catch quiet speech
    mask = energy > thresh

    # Smooth: bridge short silence gaps (<=0.30 s) and drop speech blips (<0.10 s)
    bridge = int(0.30 / FRAME_SEC)
    blip = int(0.10 / FRAME_SEC)
    mask = _close_gaps(mask, bridge)
    mask = _remove_runs(mask, blip)
    return mask


def _close_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Fill False runs shorter than max_gap (join nearby speech)."""
    out = mask.copy()
    i = 0
    n = len(mask)
    while i < n:
        if not out[i]:
            j = i
            while j < n and not out[j]:
                j += 1
            if 0 < i and j < n and (j - i) <= max_gap:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def _remove_runs(mask: np.ndarray, min_run: int) -> np.ndarray:
    """Drop True runs shorter than min_run (remove noise clicks)."""
    out = mask.copy()
    i = 0
    n = len(mask)
    while i < n:
        if out[i]:
            j = i
            while j < n and out[j]:
                j += 1
            if (j - i) < min_run:
                out[i:j] = False
            i = j
        else:
            i += 1
    return out


def run(
    audio_path: str,
    lines: List[Line],
    offset_sec: float = 0.0,
    progress: Optional[Callable[[int, str], None]] = None,
    **_ignore,
) -> List[Line]:
    """
    Assign a timestamp to every line by distributing them across detected
    speech. Returns the same list with timestamp_sec / confidence filled in.
    """
    cb = progress or (lambda p, m: None)
    cb(1, "Fast waveform sync starting...")

    energy, sr = _frame_energy(audio_path, cb)
    if energy.size == 0:
        raise RuntimeError("Could not read any audio for sync.")

    cb(45, "Detecting speech vs. silence...")
    mask = _speech_mask(energy)

    # Real time at the start of each frame.
    frame_time = np.arange(len(mask), dtype="float64") * (FRAME / sr) + offset_sec
    # Cumulative speech time after each frame (the "speech clock").
    speech_cum = np.cumsum(mask) * (FRAME / sr)
    total_speech = float(speech_cum[-1]) if speech_cum.size else 0.0
    if total_speech <= 0:
        raise RuntimeError("No speech detected in the audio.")

    # Frame indices that are speech, for fast target->time lookup.
    speech_idx = np.flatnonzero(mask)
    speech_clock = speech_cum[speech_idx]     # increasing 0..total_speech

    cb(60, "Mapping transcript lines to the speech timeline...")

    # Weight each line by how much is actually spoken on it.
    weights = []
    for ln in lines:
        t = _spoken([ln]).strip()
        weights.append(max(len(t), 1) if ln.text.strip() else 0)
    weights = np.array(weights, dtype="float64")
    total_w = float(weights.sum())
    if total_w <= 0:
        raise RuntimeError("Transcript has no spoken text to align.")

    # Cumulative weight at the MIDPOINT of each line -> fraction of speech.
    cum_before = np.concatenate([[0.0], np.cumsum(weights)[:-1]])
    mid = cum_before + weights / 2.0
    frac = mid / total_w
    target_speech = frac * total_speech

    # For each target speech-time, find the real time when the speech clock
    # reaches it (vectorised binary search).
    pos = np.searchsorted(speech_clock, target_speech, side="left")
    pos = np.clip(pos, 0, len(speech_idx) - 1)
    real_times = frame_time[speech_idx[pos]]

    n = len(lines)
    for i, ln in enumerate(lines):
        if ln.manually_set or weights[i] == 0:
            continue
        ln.timestamp_sec = round(float(real_times[i]), 3)
        ln.confidence = 0.80          # approximate waveform sync -> amber/review
        if i % 800 == 0:
            cb(60 + int(i / max(n, 1) * 38),
               f"Mapping line {i}/{n}...")

    # Enforce monotonic non-decreasing timestamps (safety).
    last = None
    for ln in lines:
        if ln.timestamp_sec is None:
            continue
        if last is not None and ln.timestamp_sec < last:
            ln.timestamp_sec = last
        last = ln.timestamp_sec

    # Fill any line that had no spoken text (blank / marker lines) so EVERY
    # line in the range is navigable: forward-fill, then back-fill the head.
    last = None
    for ln in lines:
        if ln.timestamp_sec is None and last is not None and not ln.manually_set:
            ln.timestamp_sec = last
            ln.confidence = 0.70
        elif ln.timestamp_sec is not None:
            last = ln.timestamp_sec
    nxt = None
    for ln in reversed(lines):
        if ln.timestamp_sec is None and nxt is not None and not ln.manually_set:
            ln.timestamp_sec = nxt
            ln.confidence = 0.70
        elif ln.timestamp_sec is not None:
            nxt = ln.timestamp_sec

    matched = sum(1 for ln in lines if ln.timestamp_sec is not None)
    pct = int(matched * 100 / max(len(lines), 1))
    cb(100, f"Done: {matched}/{len(lines)} lines timestamped ({pct}%). "
            f"Speech: {total_speech/60:.0f} min of {frame_time[-1]/60:.0f} min.")
    return lines
