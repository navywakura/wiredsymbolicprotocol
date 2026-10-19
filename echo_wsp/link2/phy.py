"""LINK-1's modem, for envelope v2 (75 symbols, K=1). Integers only.

Tones, greeting, sync, confirm and the per-symbol doubt for GMD are
imported from echo_wsp.link1.modem unchanged; only the symbol count and the
codec differ.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from echo_wsp.link1 import modem as m1
from echo_wsp.link2 import envelope as ev

NSYM = ev.AIR_SYMBOLS  # 75


def frame_samples() -> int:
    return (m1.PRE_PERIODS + NSYM) * m1.PERIOD


def airtime_ms() -> int:
    return frame_samples() * 1000 // m1.RATE


def modulate(raw: bytes) -> List[int]:
    nib = ev.to_air(raw)
    out = [0] * frame_samples()
    pos = 0
    for note in m1.GREETING:
        m1._tone(out, pos, m1.NOTE_PERIODS * m1.PERIOD, (note,), m1.AMP)
        pos += m1.NOTE_PERIODS * m1.PERIOD
    for j in range(NSYM):
        m1._tone(out, pos, m1.PERIOD, (m1.DATA_K1[nib[j]],), m1.AMP)
        pos += m1.PERIOD
    return [max(-32768, min(32767, v)) for v in out]


def transmit(raws: Sequence[bytes], gap: int = 2 * m1.PERIOD) -> List[int]:
    out: List[int] = []
    for r in raws:
        out.extend(modulate(r))
        out.extend([0] * gap)
    return out


@dataclass
class Heard:
    start: int
    raw: Optional[bytes]
    corrected: int


def _decode_at(x: Sequence[int], t: int):
    d = t + m1.PRE_PERIODS * m1.PERIOD
    nib: List[int] = []
    doubt: List[int] = []
    for j in range(NSYM):
        w = d + j * m1.PERIOD + m1.WIN_OFF
        best_v, best_p, second_p = 0, -1, -1
        for v, k in enumerate(m1.DATA_K1):
            p = m1._power(x, w, k)
            if p > best_p:
                best_v, best_p, second_p = v, p, best_p
            elif p > second_p:
                second_p = p
        nib.append(best_v)
        doubt.append(4096 * max(0, second_p) // best_p if best_p > 0 else 4096)
    return ev.from_air(nib, doubt)


def demodulate(x: Sequence[int], max_frames: int = 64) -> List[Heard]:
    """Every v2 frame in a recording, in time order. RS-decoded bytes only;
    CRC, MAC and replay are checked by envelope.Guard, not here."""
    x = list(x)
    flen = frame_samples()
    if len(x) < flen:
        return []
    en = m1._Energy(x)
    last = len(x) - flen
    coarse = [(m1.sync_score(x, en, t), t) for t in range(0, last + 1, m1.SYNC_HOP)]
    coarse.sort(reverse=True)
    taken: List[int] = []
    rejected: List[int] = []
    found: List[Heard] = []
    for score, t in coarse:
        if score < m1.SYNC_MIN or len(found) >= max_frames:
            break
        if any(abs(t - u) < flen - m1.PERIOD for u in taken):
            continue
        if any(abs(t - u) <= m1.SYNC_SPAN for u in rejected):
            continue
        best_t, _s = m1._refine(x, en, t, last)
        if any(abs(best_t - u) < flen - m1.PERIOD for u in taken):
            continue
        if m1.confirm_score(x, best_t) < m1.CONFIRM_MIN:
            rejected.append(t)
            continue
        taken.append(best_t)
        raw, fixed = _decode_at(x, best_t)
        found.append(Heard(start=best_t, raw=raw, corrected=fixed))
    found.sort(key=lambda h: h.start)
    return found
