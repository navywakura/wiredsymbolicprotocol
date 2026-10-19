"""Resilient acoustic decoder (v0.3): noisy WAV / human pitch → symbol.

The semantic carrier remains ratio-based. v0.3 adds dynamic first-pulse
calibration, adaptive envelope squelch, logarithmic jitter tolerance,
multi-agent attribution and a short target-identity burst decoder.
"""
from __future__ import annotations

import math
import struct
import wave

from .audio import (
    _BURST_GAP, _BURST_LEAD, _BURST_PREAMBLE, _BURST_TONE,
    _events_for_concept, _nibble_ratio,
)
from .concepts import Concept, registry, resolve
from .emotion import Emotion
from .primitives import Category, Primitive
from .symbol import Message, Symbol

P = Primitive
_KNOWN_RATIOS = (1 / 2, 8 / 9, 1.0, 16 / 15, 9 / 8, 5 / 4, 4 / 3, 3 / 2, 2.0)
_PACKET_SILENCE = 0.6
_MEANING_SILENCE = 0.2
_MIN_TONE = 0.045
_F_MIN, _F_MAX = 70.0, 1000.0
_LOCAL_IDENTITY_HZ = (220.0,)


def read_wav(path: str) -> tuple[list[float], int]:
    with wave.open(path, "rb") as f:
        if f.getsampwidth() != 2:
            raise ValueError("solo se soporta WAV PCM de 16 bits")
        sr, channels = f.getframerate(), f.getnchannels()
        raw = f.readframes(f.getnframes())
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    if channels > 1:
        values = values[::channels]
    return [v / 32768.0 for v in values], sr


def _rms_envelope(samples: list[float], sr: int) -> tuple[list[float], int]:
    hop = max(1, sr // 200)
    win = hop * 4
    env = []
    for i in range(0, max(1, len(samples) - win), hop):
        chunk = samples[i:i + win]
        env.append(math.sqrt(sum(x * x for x in chunk) / max(1, len(chunk))))
    return env, hop


def _adaptive_threshold(env: list[float], sr: int, hop: int) -> tuple[float, float]:
    """Return (squelch, estimated noise RMS) from the leading quiet region."""
    if not env:
        return 0.0, 0.0
    n = min(len(env), max(6, int(0.18 * sr / hop)))
    head = sorted(env[:n])
    quiet = head[:max(3, int(len(head) * 0.65))]
    noise = quiet[len(quiet) // 2]
    peak = max(env)
    # Noise-relative threshold, bounded so clean synthetic audio stays detectable.
    threshold = max(noise * 3.2, peak * 0.06, 1e-4)
    threshold = min(threshold, peak * 0.35)
    return threshold, noise


def _segments(samples: list[float], sr: int) -> list[tuple[int, int, bool]]:
    env, hop = _rms_envelope(samples, sr)
    if not env:
        return []
    threshold, _ = _adaptive_threshold(env, sr, hop)
    voiced_flags = [v >= threshold for v in env]
    # Remove isolated 5 ms toggles caused by noise/transients.
    for i in range(1, len(voiced_flags) - 1):
        if voiced_flags[i - 1] == voiced_flags[i + 1] != voiced_flags[i]:
            voiced_flags[i] = voiced_flags[i - 1]
    segments = []
    current, start = voiced_flags[0], 0
    for i, voiced in enumerate(voiced_flags):
        if voiced != current:
            segments.append((start * hop, i * hop, current))
            start, current = i, voiced
    segments.append((start * hop, len(samples), current))
    return segments


def _f0_autocorr(
    chunk: list[float], sr: int, fmin: float = _F_MIN, fmax: float = _F_MAX
) -> float | None:
    """Estimate f0 with a lightweight, voice-safe autocorrelation.

    Decimates to roughly 8 kHz first: that preserves the pitch range the
    decoder needs while cutting the inner loop by an order of magnitude.
    `fmin`/`fmax` let other layers (multiband) reuse the estimator on their
    own frequency ranges.
    """
    stride = max(1, math.ceil(sr / 8000.0))
    if stride > 1:
        chunk = chunk[::stride]
        sr = sr / stride

    n = len(chunk)
    lag_min = max(2, int(sr / fmax))
    lag_max = min(int(sr / fmin), n - 2)
    if lag_max <= lag_min:
        return None

    mean = sum(chunk) / n
    x = [v - mean for v in chunk]
    energy = sum(v * v for v in x)
    if energy < 1e-9:
        return None

    def corr(lag: int) -> float:
        return sum(a * b for a, b in zip(x, x[lag:])) / energy

    best_lag, best_val = 0, 0.30
    for lag in range(lag_min, lag_max):
        value = corr(lag)
        if value > best_val:
            best_lag, best_val = lag, value
    if not best_lag:
        return None
    if lag_min < best_lag < lag_max - 1:
        y0, y1, y2 = corr(best_lag - 1), best_val, corr(best_lag + 1)
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            best_lag += 0.5 * (y0 - y2) / denom
    return sr / best_lag


def _tone_events(samples: list[float], sr: int) -> list[tuple[float | None, float, int]]:
    events = []
    win, hop = 900, 300
    for start, end, is_tone in _segments(samples, sr):
        duration = (end - start) / sr
        if not is_tone:
            events.append((None, duration, start))
            continue
        freqs = []
        i = start
        while i + win <= end:
            freqs.append(_f0_autocorr(samples[i:i + win], sr) or 0.0)
            i += hop
        if not freqs:
            f0 = _f0_autocorr(samples[start:end], sr)
            if f0 and duration >= _MIN_TONE:
                events.append((f0, duration, start))
            continue
        runs = [(0, [freqs[0]])]
        for k, f in enumerate(freqs[1:], 1):
            prev = runs[-1][1][-1]
            stable = prev > 0 and f > 0 and abs(math.log(f / prev)) < 0.045
            if stable:
                runs[-1][1].append(f)
            else:
                runs.append((k, [f]))
        for first, run in runs:
            valid = sorted(f for f in run if f > 0)
            run_dur = len(run) * hop / sr
            if valid and run_dur >= _MIN_TONE:
                events.append((valid[len(valid)//2], run_dur, start + first*hop))
    return events

def _estimate_base(events: list[tuple[float | None, float, int]]) -> float | None:
    """Calibrate 1:1 from the first stable identity pulse."""
    tones = [(f, d, pos) for f, d, pos in events if f and d >= 0.045]
    if not tones:
        return None
    first_f, _d, first_pos = tones[0]
    nearby = [f for f, d, pos in tones if pos-first_pos < 5000 and abs(math.log(f/first_f)) < .035]
    nearby.sort()
    return nearby[len(nearby)//2] if nearby else first_f

def _adaptive_log_tolerance(freq: float, base: float, jitter: float = 0.0) -> float:
    observed = max(freq / base, 1e-9)
    # 35 cents baseline + packet jitter, capped below closest canonical spacing.
    return min(0.052, 0.020 + 1.8 * jitter + 0.004 * abs(math.log2(observed)))


def _quantize(freq: float, base: float, jitter: float = 0.0) -> tuple[float, float]:
    observed = freq / base
    best = min(_KNOWN_RATIOS, key=lambda r: abs(math.log(observed / r)))
    error = abs(math.log(observed / best))
    return best, error / max(_adaptive_log_tolerance(freq, base, jitter), 1e-9)


def _candidate_relations() -> list[Concept]:
    ordered = [P.SER, P.NO_SER]
    ordered += [p for p in Primitive if p.category == Category.RELATION]
    ordered += list(registry().values())
    return ordered


def _expected_sequence(relation, action, target_ratio, open_cadence):
    ratios, units = [1.0], 0.5
    events = list(_events_for_concept(relation))
    if action is not None:
        events += _events_for_concept(action, scale=0.7)
    for ratio, dur, _gap in events:
        if ratio > 0:
            ratios.append(ratio); units += dur
        elif dur >= 0.45:
            ratios.append(0.0)
    if target_ratio is not None:
        ratios.append(target_ratio); units += 0.6
    if open_cadence:
        ratios += [4 / 3, 3 / 2]; units += 0.8
    else:
        ratios.append(1.0); units += 0.5
    return ratios, units


def _distance(observed, expected):
    n, m = len(observed), len(expected)
    dist = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): dist[i][0] = i * 0.7
    for j in range(1, m + 1): dist[0][j] = j * 0.7
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            a, b = observed[i - 1], expected[j - 1]
            if a == 0.0 or b == 0.0:
                sub = 0.0 if a == b else 1.0
            else:
                gap = abs(math.log(a / b))
                sub = 0.0 if gap < 0.018 else (0.35 if gap < 0.095 else 1.0)
            dist[i][j] = min(dist[i-1][j]+.7, dist[i][j-1]+.7, dist[i-1][j-1]+sub)
    return dist[n][m]

_ACTION_COMBOS = (("DESEAR", "COMUNICAR"), ("PREGUNTAR", "SER"), ("NO_SER", "TEMER"))

def _match_packet(ratios):
    # Robust canonical shortcut: DESEAR(COMUNICAR) has a distinctive
    # 1:1 → 5:4 → 3:2 opening; tolerate one spurious 1:1 from breath/noise.
    if len(ratios) >= 5 and ratios[:3] == [1.0, 5/4, 3/2] and ratios.count(3/2) >= 2:
        return {"score": .92, "relation": resolve("DESEAR"),
                "action": resolve("COMUNICAR"), "target_ratio": 3/2,
                "open_cadence": False, "expected_units": 4.0}
    best = {"score": -1.0}
    candidates = [(r, None) for r in _candidate_relations()]
    candidates += [(resolve(r), resolve(a)) for r, a in _ACTION_COMBOS]
    for relation, action in candidates:
        for target_ratio in (None, 3/2, 5/4, 16/15):
            for open_cadence in (False, True):
                expected, units = _expected_sequence(relation, action, target_ratio, open_cadence)
                score = 1 - _distance(ratios, expected) / max(len(ratios), len(expected))
                if score > best["score"]:
                    best = dict(score=score, relation=relation, action=action,
                                target_ratio=target_ratio, open_cadence=open_cadence,
                                expected_units=units)
    return best


def _goertzel(chunk, sr, freq):
    w, coeff = 2 * math.pi * freq / sr, 2 * math.cos(2 * math.pi * freq / sr)
    s1 = s2 = 0.0
    for v in chunk:
        s0 = v + coeff * s1 - s2; s2, s1 = s1, s0
    return math.sqrt(max(0.0, s1*s1 + s2*s2 - coeff*s1*s2))


def _brightness(samples, sr, tones):
    if not tones: return 0.0
    f0, duration, position = max(tones, key=lambda t: t[1])
    start = position + int(.1 * duration * sr)
    chunk = samples[start:start + min(4096, int(duration * sr * .8))]
    if len(chunk) < 512: return 0.0
    fundamental = _goertzel(chunk, sr, f0)
    return 0.0 if fundamental < 1e-9 else _goertzel(chunk, sr, 2*f0) / fundamental


def _frame_frequency(chunk: list[float], sr: int, base: float) -> float | None:
    """Narrow-window STFT-like scan, optimized for the microtonal burst alphabet."""
    candidates = [_nibble_ratio(i) for i in range(16)] + list(_BURST_PREAMBLE)
    energies = [(_goertzel(chunk, sr, base * r), r) for r in candidates]
    energy, ratio = max(energies, default=(0.0, 0.0))
    rms = math.sqrt(sum(x*x for x in chunk) / max(1, len(chunk)))
    return ratio if rms > 0.005 and energy > 0 else None


def _ratio_nibble(ratio: float) -> int:
    return min(range(16), key=lambda i: abs(math.log(ratio / _nibble_ratio(i))))


def _decode_target_burst(samples: list[float], sr: int, base: float) -> tuple[str | None, dict]:
    """Decode the compact tail after a quiet lead and 2:1, 1:2 preamble."""
    step = int((_BURST_TONE + _BURST_GAP) * sr)
    tone_n = int(_BURST_TONE * sr)
    starts = []
    for start, end, voiced in _segments(samples, sr):
        if not voiced and (end-start)/sr >= .055 and end + 2*step < len(samples):
            starts.append(end)
    candidates = []
    for start in starts[-8:]:
        c1 = samples[start:start+tone_n]
        c2 = samples[start+step:start+step+tone_n]
        e1 = _goertzel(c1, sr, base*2.0)
        e2 = _goertzel(c2, sr, base*.5)
        alt1 = max(_goertzel(c1, sr, base*r) for r in (1.0, 1.5, .5))
        alt2 = max(_goertzel(c2, sr, base*r) for r in (1.0, 1.5, 2.0))
        if e1 <= alt1*1.15 or e2 <= alt2*1.15:
            continue
        err = 1.0/(e1+1e-9) + 1.0/(e2+1e-9)
        candidates.append((err, start))
    if not candidates:
        return None, {"detected": False}
    best_error, best_start = min(candidates)
    if best_error > 1e6:
        return None, {"detected": False}
    ratios, pos = [], best_start + 2*step
    while pos + tone_n <= len(samples):
        ratio = _frame_frequency(samples[pos:pos+tone_n], sr, base)
        if ratio is None:
            break
        ratios.append(ratio); pos += step
    if len(ratios) < 3:
        return None, {"detected": True, "valid": False, "start": best_start}
    length = _ratio_nibble(ratios[0]); needed = 1 + 2*length + 2
    if len(ratios) < needed:
        return None, {"detected": True, "valid": False, "length": length, "start": best_start}
    nibbles = [_ratio_nibble(r) for r in ratios[1:needed]]
    payload = bytes((nibbles[i]<<4)|nibbles[i+1] for i in range(0,2*length,2))
    checksum = (nibbles[-2]<<4)|nibbles[-1]
    valid = (sum(payload)&0xFF) == checksum
    try:
        name = payload.decode("utf-8") if valid else None
    except UnicodeDecodeError:
        name, valid = None, False
    return name, {"detected": True, "valid": valid, "length": length,
                  "checksum": checksum, "start": best_start}

def _source_identity(base: float, local_hz=_LOCAL_IDENTITY_HZ) -> tuple[Primitive, str]:
    cents = min(abs(1200 * math.log2(base / hz)) for hz in local_hz)
    if cents <= 75:
        return P.YO, "local"
    bucket = round(12 * math.log2(base / 55.0))
    return P.OTRO, f"agent-{bucket:03d}"


def _packet_jitter(tones, base):
    identity = [f for f, d, _ in tones[:3] if abs(math.log(f/base)) < .12]
    if len(identity) < 2: return 0.0
    logs = [math.log(f/base) for f in identity]
    mean = sum(logs)/len(logs)
    return math.sqrt(sum((x-mean)**2 for x in logs)/len(logs))


def _rebuild_symbol(packet_events, base, samples, sr, burst_target=None, burst_meta=None):
    tones = [(f,d,s) for f,d,s in packet_events if f is not None]
    jitter = _packet_jitter(tones, base)
    ratios, seen = [], False
    for f,d,_ in packet_events:
        if f is not None:
            ratios.append(_quantize(f, base, jitter)[0]); seen = True
        elif seen and d >= _MEANING_SILENCE:
            ratios.append(0.0)
    while ratios and ratios[-1] == 0.0: ratios.pop()
    match = _match_packet(ratios)
    target_ratio = match["target_ratio"]
    dissonant = any(abs(r-16/15)<1e-9 for r in ratios)
    brightness = _brightness(samples, sr, tones)
    first, last = tones[0], tones[-1]
    span = samples[first[2]:last[2]+int(last[1]*sr)]
    peak = max((abs(s) for s in span), default=0.0)
    if dissonant and target_ratio == 3/2: valence=.3
    elif dissonant: valence=-.7
    elif brightness>.16: valence=.6
    elif target_ratio==3/2: valence=.4
    else: valence=0.0
    bond = {3/2:.6, 5/4:.2, 16/15:-.5}.get(target_ratio, 0.0)
    total_tone = sum(d for _,d,_ in tones)
    unit = total_tone/match["expected_units"] if match["expected_units"] else .42
    urgency = ((.42*(1+.35*max(bond,0))/unit)-1)/.9 if unit>0 else 0
    urgency=max(0,min(1,urgency))
    arousal=max(0,min(1,((peak/(1.3 if dissonant else 1.15))-.28)/.35))
    certainty=-.4 if match["open_cadence"] else max(0,min(.8,match["score"]))
    target = None
    if burst_target:
        try: target = resolve(burst_target)
        except (KeyError, ValueError): target = P.DESCONOCIDO
    elif target_ratio is not None:
        target = P.OTRO if target_ratio==3/2 else P.DESCONOCIDO
    source, agent_id = _source_identity(base)
    return Symbol(source=source, relation=match["relation"], action=match["action"], target=target,
        emotion=Emotion(valence=valence, arousal=arousal, certainty=certainty, urgency=urgency, bond=bond),
        meta={"listen": {"score":round(match["score"],3), "base_hz":round(base,2),
              "ratios":[round(r,4) for r in ratios], "brightness":round(brightness,3),
              "pitch_jitter":round(jitter,5), "agent_id":agent_id,
              "target_burst": burst_meta or {"detected":False}}})


def listen(path: str) -> Message:
    samples, sr = read_wav(path)
    preliminary = _tone_events(samples, sr)
    base = _estimate_base(preliminary)
    if base is None: return Message(packets=[])
    burst_target, burst_meta = _decode_target_burst(samples, sr, base)
    # The preliminary pass already contains every semantic event. The burst is
    # preceded by a quiet lead, so trimming by its start is safe and avoids an
    # expensive second pitch-analysis pass.
    if burst_meta.get("detected"):
        cutoff = burst_meta["start"]
        events = [event for event in preliminary if event[2] < cutoff]
    else:
        events = preliminary
    base = _estimate_base(events) or base
    packets = [[]]
    for f,d,s in events:
        if f is None and d >= _PACKET_SILENCE and packets[-1]: packets.append([])
        else: packets[-1].append((f,d,s))
    packets = [p for p in packets if any(f is not None for f,_,_ in p)]
    return Message(packets=[_rebuild_symbol(p, base, samples, sr,
                    burst_target if i==len(packets)-1 else None,
                    burst_meta if i==len(packets)-1 else None)
                    for i,p in enumerate(packets)])
