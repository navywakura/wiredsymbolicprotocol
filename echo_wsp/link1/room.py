"""A simulated room between a speaker and a microphone.

This is the world, not the agent, so it may use floats (Gaussian noise).
The agent's side — modem, envelope, RS, CRC — stays integer.

Impairments, all seeded:
    lead      0..8000 samples of silence before the first frame
    multipath 'dry'  : direct + one close reflection
              'echo' : six taps out to 56 ms, beyond the 8 ms guard
    noise     white Gaussian at a fixed SNR over the active signal
    whistle   an interfering tone that jumps every 300 ms (optional)
    ppm       sample-clock mismatch, linear interpolation (optional)
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence

ROOMS = {
    "dry": ((0, 1.0), (7, 0.3)),
    "echo": ((0, 1.0), (23, 0.6), (71, -0.4), (160, 0.3), (420, 0.2), (900, 0.1)),
}


def _convolve(x: Sequence[int], taps) -> List[float]:
    span = max(d for d, _ in taps)
    out = [0.0] * (len(x) + span)
    for d, g in taps:
        for i, v in enumerate(x):
            if v:
                out[i + d] += g * v
    return out


def _resample(x: Sequence[float], ppm: float) -> List[float]:
    if not ppm:
        return list(x)
    ratio = 1.0 + ppm * 1e-6
    n = int(len(x) / ratio)
    out = []
    for i in range(n):
        p = i * ratio
        j = int(p)
        f = p - j
        a = x[j]
        b = x[j + 1] if j + 1 < len(x) else 0.0
        out.append(a + (b - a) * f)
    return out


def simulate(x: Sequence[int], *, snr_db: float, room: str = "dry",
             seed: int = 0, whistle: bool = False, ppm: float = 0.0,
             tail: int = 4000) -> List[int]:
    rng = random.Random(seed)
    lead = rng.randrange(0, 8001)
    y = _convolve(x, ROOMS[room])
    y = _resample(y, ppm)
    active = [v for v in y if v]
    ps = sum(v * v for v in active) / max(1, len(active))
    sigma = math.sqrt(ps / (10.0 ** (snr_db / 10.0))) if ps else 0.0
    total = [0.0] * lead + y + [0.0] * tail
    if whistle:
        amp = math.sqrt(ps) * 0.5
        hop = 4800
        for s in range(0, len(total), hop):
            f = rng.uniform(1000.0, 3200.0)
            ph = rng.uniform(0, 2 * math.pi)
            for i in range(s, min(len(total), s + hop)):
                total[i] += amp * math.sin(ph + 2 * math.pi * f * i / 16000.0)
    out = []
    for v in total:
        w = v + rng.gauss(0.0, sigma)
        out.append(max(-32768, min(32767, int(round(w)))))
    return out
