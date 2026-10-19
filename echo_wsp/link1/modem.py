"""Integer MFSK modem for LINK-1 frames. 16 kHz, mono, int16 samples.

Air format for one 22-byte frame:

    greeting   5 notes x 2 symbol periods  (RE MI DO DO, SOL, as in WSP v0.4)
    data       60 code nibbles (K=1) or 30 symbols of two nibbles (K=2)

A symbol period is 640 samples (40 ms): the first 128 are a guard that
soaks up echoes of the previous tone, and the power of each candidate tone
is measured over a 512-sample window starting at offset 96. Every tone
sits on an exact DFT bin of that window (bin width 31.25 Hz), so the
power is a plain integer correlation against integer cosine and sine
rows: no float, no FFT, no window function.

The sine table is computed once at import and its SHA-256 is pinned by
tests/test_link1.py; modulation and demodulation use integers only.

Tones (bins):
    K=1  data  36 + 4j        1125 .. 3000 Hz   one tone, 4 bits / symbol
    K=2  data  36 + 3j  and   88 + 3j           two tones, 8 bits / symbol
    greeting   72 81 64 32 48  = 2250 2531 2000 1000 1500 Hz
               ratios 1 : 9/8 : 8/9 : 4/9 : 2/3 of RE
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from itertools import accumulate
from operator import mul
from typing import Dict, List, Optional, Sequence

from echo_wsp.link1 import frame as fr

RATE = 16000
N = 512
GUARD = 128
PERIOD = N + GUARD  # 640 samples, 40 ms
WIN_OFF = 96
RAMP = 32
FULL = 32767
AMP = 14000

DATA_K1 = tuple(36 + 4 * j for j in range(16))
DATA_K2 = (tuple(36 + 3 * j for j in range(16)),
           tuple(88 + 3 * j for j in range(16)))
GREETING = (72, 81, 64, 32, 48)
NOTE_PERIODS = 2
PRE_PERIODS = NOTE_PERIODS * len(GREETING)  # 10

SYNC_HOP = 64
# Coarse stage: sum of per-mille broadband purity over 5 notes x 2 windows,
# max 10000. Broadband purity throws away the correlation's processing
# gain (white noise at -5 dB already caps it near 2600), so it only
# nominates candidates; the confirm stage decides.
SYNC_MIN = 1500
# Confirm stage: per-mille dominance of each note over the other four
# greeting bins in the same window, summed over the 10 windows.
CONFIRM_MIN = 7000
SYNC_SPAN = 2 * SYNC_HOP
SYNC_STEP = 4

SIN = tuple(int(round(FULL * math.sin(2 * math.pi * m / N))) for m in range(N))
COS = tuple(SIN[(m + N // 4) % N] for m in range(N))
TABLE_SHA256 = hashlib.sha256(
    b"".join(v.to_bytes(2, "little", signed=True) for v in SIN)).hexdigest()

_RAMP_UP = tuple((j + 1) * FULL // (RAMP + 1) for j in range(RAMP))
_ROWS: Dict[int, tuple] = {}


def _rows(k: int) -> tuple:
    r = _ROWS.get(k)
    if r is None:
        r = (tuple(COS[(k * i) % N] for i in range(N)),
             tuple(SIN[(k * i) % N] for i in range(N)))
        _ROWS[k] = r
    return r


def symbols_for(k_tones: int) -> int:
    if k_tones == 1:
        return fr.AIR_SYMBOLS
    if k_tones == 2:
        return fr.AIR_SYMBOLS // 2
    raise ValueError("K must be 1 or 2")


def frame_samples(k_tones: int = 1) -> int:
    return (PRE_PERIODS + symbols_for(k_tones)) * PERIOD


def airtime_ms(k_tones: int = 1) -> int:
    return frame_samples(k_tones) * 1000 // RATE


def _tone(out: List[int], start: int, length: int, bins: Sequence[int],
          amp: int) -> None:
    """Add a ramped tone (or a chord of tones) to out[start:start+length]."""
    for i in range(length):
        n = start + i
        if i < RAMP:
            env = _RAMP_UP[i]
        elif i >= length - RAMP:
            env = _RAMP_UP[length - 1 - i]
        else:
            env = FULL
        acc = 0
        for k in bins:
            acc += SIN[(k * n) % N]
        out[n] += ((acc * amp) >> 15) * env >> 15


def modulate(raw: bytes, k_tones: int = 1) -> List[int]:
    """22 frame bytes -> int16 samples (greeting + data), no lead silence."""
    nib = fr.to_air(raw)
    nsym = symbols_for(k_tones)
    out = [0] * frame_samples(k_tones)
    pos = 0
    for note in GREETING:
        _tone(out, pos, NOTE_PERIODS * PERIOD, (note,), AMP)
        pos += NOTE_PERIODS * PERIOD
    for j in range(nsym):
        if k_tones == 1:
            _tone(out, pos, PERIOD, (DATA_K1[nib[j]],), AMP)
        else:
            _tone(out, pos, PERIOD,
                  (DATA_K2[0][nib[2 * j]], DATA_K2[1][nib[2 * j + 1]]), AMP // 2)
        pos += PERIOD
    return [max(-32768, min(32767, v)) for v in out]


def _power(x: Sequence[int], start: int, k: int) -> int:
    c, s = _rows(k)
    w = x[start:start + N]
    re = sum(map(mul, w, c))
    im = sum(map(mul, w, s))
    return re * re + im * im


class _Energy:
    """Prefix sums of x^2 so a window's energy costs O(1)."""

    def __init__(self, x: Sequence[int]) -> None:
        self.p = [0] + list(accumulate(v * v for v in x))

    def win(self, start: int) -> int:
        return self.p[start + N] - self.p[start]


# A pure tone of amplitude a on an exact bin: power = (a*FULL*N/2)^2 and
# energy = a^2*N/2, so purity = power / (energy * FULL^2 * N/2) -> 1.
_PURITY_DEN = FULL * FULL * (N // 2)


def _purity(x: Sequence[int], en: _Energy, start: int, k: int) -> int:
    e = en.win(start)
    if e <= 0:
        return 0
    return min(1000, 1000 * _power(x, start, k) // (e * _PURITY_DEN))


def sync_score(x: Sequence[int], en: _Energy, t: int) -> int:
    """Purity of each greeting note in each of its symbol windows.

    Two windows per note: a note lasts two periods, and with one window the
    score is flat across almost a whole period, so the decoder would slide
    into the next symbol. With both, a late start puts the second window
    on the next note and the score falls.
    """
    score = 0
    for q, note in enumerate(GREETING):
        base = t + q * NOTE_PERIODS * PERIOD + WIN_OFF
        for p in range(NOTE_PERIODS):
            score += _purity(x, en, base + p * PERIOD, note)
    return score


@dataclass
class Heard:
    start: int  # sample index of the greeting
    score: int  # sync score, 0..10000
    raw: Optional[bytes]  # 22 bytes after RS, or None
    frame: Optional[fr.Frame]  # parsed and CRC-checked, or None
    corrected: int  # RS symbols corrected, -1 on RS failure


def _decode_at(x: Sequence[int], t: int, k_tones: int) -> tuple:
    """Hard decisions plus, per symbol, how close the runner-up came.

    doubt = 4096 * second / best: 0 for a clean tone, 4096 for a coin toss.
    """
    d = t + PRE_PERIODS * PERIOD
    nib: List[int] = []
    doubt: List[int] = []
    groups = (DATA_K1,) if k_tones == 1 else DATA_K2
    for j in range(symbols_for(k_tones)):
        w = d + j * PERIOD + WIN_OFF
        for g in groups:
            best_v, best_p, second_p = 0, -1, -1
            for v, k in enumerate(g):
                p = _power(x, w, k)
                if p > best_p:
                    best_v, best_p, second_p = v, p, best_p
                elif p > second_p:
                    second_p = p
            nib.append(best_v)
            doubt.append(4096 * max(0, second_p) // best_p if best_p > 0 else 4096)
    return fr.from_air(nib, doubt)


def confirm_score(x: Sequence[int], t: int) -> int:
    """How much each note owns its window among the five greeting bins.

    Narrowband against narrowband, so noise spread over 8 kHz barely
    moves it, and a data tone that happens to sit on one greeting bin
    cannot fake the other nine windows.
    """
    total = 0
    for q, note in enumerate(GREETING):
        base = t + q * NOTE_PERIODS * PERIOD + WIN_OFF
        for p in range(NOTE_PERIODS):
            w = base + p * PERIOD
            pw = {k: _power(x, w, k) for k in GREETING}
            den = sum(pw.values())
            total += (1000 * pw[note] // den) if den else 0
    return total


def _refine(x: Sequence[int], en: _Energy, t: int, last: int) -> tuple:
    """Centre of the sync plateau around a coarse hit.

    Every window is pure for starts in [-64, 0] samples of the true one
    (ramps of 32 at the front, WIN_OFF + N = 608 at the back), so the score
    is a plateau of ~64 samples whose centre is 32 early: exactly the middle
    of the safe range for the data windows too.
    """
    lo, hi = max(0, t - SYNC_SPAN), min(last, t + SYNC_SPAN)
    pts = [(u, sync_score(x, en, u)) for u in range(lo, hi + 1, SYNC_STEP)]
    peak_i = max(range(len(pts)), key=lambda i: pts[i][1])
    m = pts[peak_i][1]
    floor = m - m // 32
    left = right = peak_i
    while left > 0 and pts[left - 1][1] >= floor:
        left -= 1
    while right < len(pts) - 1 and pts[right + 1][1] >= floor:
        right += 1
    centre = (pts[left][0] + pts[right][0]) // 2
    return centre, m


def demodulate(x: Sequence[int], k_tones: int = 1,
               max_frames: int = 64) -> List[Heard]:
    """Find and decode every frame in a recording. Integers only.

    Frames that fail RS or CRC come back with frame=None and are never
    handed to an agent. Returned in time order.
    """
    x = list(x)
    flen = frame_samples(k_tones)
    if len(x) < flen:
        return []
    en = _Energy(x)
    last = len(x) - flen
    coarse = [(sync_score(x, en, t), t) for t in range(0, last + 1, SYNC_HOP)]
    coarse.sort(reverse=True)
    taken: List[int] = []
    rejected: List[int] = []
    found: List[Heard] = []
    for score, t in coarse:
        if score < SYNC_MIN or len(found) >= max_frames:
            break
        if any(abs(t - u) < flen - PERIOD for u in taken):
            continue
        if any(abs(t - u) <= SYNC_SPAN for u in rejected):
            continue
        best_t, best_s = _refine(x, en, t, last)
        if any(abs(best_t - u) < flen - PERIOD for u in taken):
            continue
        if confirm_score(x, best_t) < CONFIRM_MIN:
            rejected.append(t)
            continue
        taken.append(best_t)
        raw, fixed = _decode_at(x, best_t, k_tones)
        f = fr.parse(raw) if raw is not None else None
        found.append(Heard(start=best_t, score=best_s, raw=raw, frame=f,
                           corrected=fixed))
    found.sort(key=lambda h: h.start)
    return found


def transmit(frames: Sequence[fr.Frame], k_tones: int = 1,
             gap: int = 2 * PERIOD) -> List[int]:
    """Several frames back to back with a short silence between them."""
    out: List[int] = []
    for f in frames:
        out.extend(modulate(f.to_bytes(), k_tones))
        out.extend([0] * gap)
    return out
