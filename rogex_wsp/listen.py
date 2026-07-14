"""Intérprete sonoro (v0.2 «Signal Return»): WAV → símbolo.

El camino de vuelta del render sonoro. No busca palabras: busca
relaciones de frecuencia. Pipeline:

    1. envolvente RMS  → segmentos de tono y silencio
    2. autocorrelación → frecuencia fundamental por tramo (con partición
                         cuando el tono salta dentro de un mismo segmento)
    3. tono base       → el clúster de frecuencia más grave
    4. cuantización    → cada tono se aproxima al ratio conocido más cercano
    5. emparejamiento  → la secuencia de ratios se compara (distancia de
                         edición) contra las firmas de todas las relaciones
    6. emoción         → tempo→urgencia, pico→activación, disonancia/brillo
                         →valencia, cadencia→certeza, destino→vínculo

El silencio se interpreta por duración: los silencios internos con
significado (ausencia/negación: NO_SER, OLVIDAR, IMPOSIBLE) entran en el
emparejamiento como marcadores; solo los silencios largos (≥0.6 s, el
separador que emite el sintetizador) parten el mensaje en paquetes.

La reconstrucción es aproximada por diseño: el eje de certeza del paquete
refleja la calidad del emparejamiento. Limitaciones documentadas: el audio
no transporta tiempo/espacio ni la identidad exacta del destino, y se
asume origen YO (tono base = 1:1).
"""

from __future__ import annotations

import math
import struct
import wave

from .audio import _events_for_concept
from .concepts import Concept, registry, resolve
from .emotion import Emotion
from .primitives import Category, Primitive
from .symbol import Message, Symbol

P = Primitive

# Ratios que el sintetizador puede emitir (ver audio.py y SPEC §5.1).
_KNOWN_RATIOS: tuple[float, ...] = (1 / 2, 8 / 9, 1.0, 16 / 15, 9 / 8, 5 / 4, 4 / 3, 3 / 2, 2.0)

_PACKET_SILENCE = 0.6    # s: silencios así de largos separan paquetes
_MEANING_SILENCE = 0.2   # s: silencios internos con significado (ausencia/negación)
_MIN_TONE = 0.045        # s: tonos más cortos se descartan como transitorios
_F_MIN, _F_MAX = 80.0, 700.0


# -- lectura y segmentación ----------------------------------------------------

def read_wav(path: str) -> tuple[list[float], int]:
    """Lee un WAV PCM de 16 bits (mono o multicanal: usa el primer canal)."""
    with wave.open(path, "rb") as f:
        if f.getsampwidth() != 2:
            raise ValueError("solo se soporta WAV PCM de 16 bits")
        sr = f.getframerate()
        channels = f.getnchannels()
        raw = f.readframes(f.getnframes())
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    if channels > 1:
        values = values[::channels]
    return [v / 32768.0 for v in values], sr


def _rms_envelope(samples: list[float], sr: int) -> tuple[list[float], int]:
    hop = max(1, sr // 200)  # ~5 ms
    win = hop * 4
    env = []
    for i in range(0, max(1, len(samples) - win), hop):
        chunk = samples[i : i + win]
        env.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)))
    return env, hop


def _segments(samples: list[float], sr: int) -> list[tuple[int, int, bool]]:
    """Segmentos (inicio, fin, es_tono) en muestras, por umbral de envolvente."""
    env, hop = _rms_envelope(samples, sr)
    if not env:
        return []
    threshold = max(env) * 0.06
    segments: list[tuple[int, int, bool]] = []
    current = env[0] >= threshold
    start = 0
    for i, value in enumerate(env):
        voiced = value >= threshold
        if voiced != current:
            segments.append((start * hop, i * hop, current))
            start, current = i, voiced
    segments.append((start * hop, len(samples), current))
    return segments


# -- detección de tono -----------------------------------------------------------

def _f0_autocorr(chunk: list[float], sr: int) -> float | None:
    """Frecuencia fundamental por autocorrelación normalizada (con refinado)."""
    n = len(chunk)
    lag_min = max(2, int(sr / _F_MAX))
    lag_max = min(int(sr / _F_MIN), n - 2)
    if lag_max <= lag_min:
        return None
    mean = sum(chunk) / n
    x = [v - mean for v in chunk]
    energy = sum(v * v for v in x)
    if energy < 1e-9:
        return None

    def corr(lag: int) -> float:
        return sum(x[i] * x[i + lag] for i in range(n - lag)) / energy

    best_lag, best_val = 0, 0.35  # exige correlación mínima
    for lag in range(lag_min, lag_max):
        value = corr(lag)
        if value > best_val:
            best_lag, best_val = lag, value
    if best_lag == 0:
        return None
    # refinado parabólico alrededor del pico
    if lag_min < best_lag < lag_max - 1:
        y0, y1, y2 = corr(best_lag - 1), best_val, corr(best_lag + 1)
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            best_lag += 0.5 * (y0 - y2) / denom
    return sr / best_lag


def _tone_events(samples: list[float], sr: int) -> list[tuple[float | None, float, int]]:
    """Lista de eventos (frecuencia|None, duración s, inicio en muestras).

    None = silencio. Dentro de un mismo segmento sonoro, se parte el evento
    cuando el tono salta de forma sostenida (dos tonos contiguos sin silencio).
    """
    events: list[tuple[float | None, float, int]] = []
    win, hop = 900, 300
    for start, end, is_tone in _segments(samples, sr):
        duration = (end - start) / sr
        if not is_tone:
            events.append((None, duration, start))
            continue
        # pista de tono por tramas
        freqs: list[float] = []
        i = start
        while i + win <= end:
            f0 = _f0_autocorr(samples[i : i + win], sr)
            freqs.append(f0 if f0 else 0.0)
            i += hop
        if not freqs:
            f0 = _f0_autocorr(samples[start:end], sr)
            if f0 and duration >= _MIN_TONE:
                events.append((f0, duration, start))
            continue
        # agrupa tramas contiguas con tono estable (±4.5 %)
        runs: list[tuple[int, list[float]]] = [(0, [freqs[0]])]
        for k, f in enumerate(freqs[1:], start=1):
            prev = runs[-1][1][-1]
            if prev > 0 and f > 0 and abs(f - prev) / prev < 0.045:
                runs[-1][1].append(f)
            else:
                runs.append((k, [f]))
        for first_frame, run in runs:
            valid = sorted(f for f in run if f > 0)
            run_dur = len(run) * hop / sr
            if valid and run_dur >= _MIN_TONE:
                events.append((valid[len(valid) // 2], run_dur, start + first_frame * hop))
    return events


# -- base y cuantización -----------------------------------------------------------

def _estimate_base(events: list[tuple[float | None, float, int]]) -> float | None:
    """Tono base = mediana del clúster de frecuencia más grave (asume origen 1:1)."""
    tones = sorted((f, d) for f, d, _ in events if f)
    if not tones:
        return None
    clusters: list[list[tuple[float, float]]] = [[tones[0]]]
    for f, d in tones[1:]:
        if abs(f - clusters[-1][-1][0]) / clusters[-1][-1][0] < 0.035:
            clusters[-1].append((f, d))
        else:
            clusters.append([(f, d)])
    # el clúster más grave con soporte suficiente (≥0.1 s en total)
    for cluster in clusters:
        if sum(d for _, d in cluster) >= 0.1:
            freqs = sorted(f for f, _ in cluster)
            return freqs[len(freqs) // 2]
    freqs = sorted(f for f, _ in clusters[0])
    return freqs[len(freqs) // 2]


def _quantize(freq: float, base: float) -> tuple[float, float]:
    """(ratio conocido más cercano, error relativo)."""
    observed = freq / base
    best = min(_KNOWN_RATIOS, key=lambda r: abs(math.log(observed / r)))
    return best, abs(math.log(observed / best))


# -- emparejamiento contra las firmas de relación -----------------------------------

def _candidate_relations() -> list[Concept]:
    ordered: list[Concept] = [P.SER, P.NO_SER]
    ordered += [p for p in Primitive if p.category == Category.RELATION]
    ordered += list(registry().values())
    return ordered


def _expected_sequence(
    relation: Concept, action: Concept | None, target_ratio: float | None, open_cadence: bool
) -> tuple[list[float], float]:
    """(secuencia de ratios esperada, unidades de duración sonora totales)."""
    ratios: list[float] = [1.0]  # pulso de identidad del origen (YO)
    units = 0.5
    events = list(_events_for_concept(relation))
    if action is not None:
        events += _events_for_concept(action, scale=0.7)
    for ratio, dur, _gap in events:
        if ratio > 0:
            ratios.append(ratio)
            units += dur
        elif dur >= 0.45:
            # silencio con significado (ausencia/negación): marcador 0.0
            ratios.append(0.0)
    if target_ratio is not None:
        ratios.append(target_ratio)
        units += 0.6
    if open_cadence:
        ratios += [4 / 3, 3 / 2]
        units += 0.8
    else:
        ratios.append(1.0)
        units += 0.5
    return ratios, units


def _distance(observed: list[float], expected: list[float]) -> float:
    """Distancia de edición con sustitución suave entre ratios vecinos."""
    n, m = len(observed), len(expected)
    dist = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dist[i][0] = i * 0.7
    for j in range(1, m + 1):
        dist[0][j] = j * 0.7
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            a, b = observed[i - 1], expected[j - 1]
            if a == 0.0 or b == 0.0:  # marcador de silencio (ausencia)
                sub = 0.0 if a == b else 1.0
            else:
                gap = abs(math.log(a / b))
                if gap < 0.01:
                    sub = 0.0
                elif gap < 0.09:
                    sub = 0.4
                else:
                    sub = 1.0
            dist[i][j] = min(
                dist[i - 1][j] + 0.7, dist[i][j - 1] + 0.7, dist[i - 1][j - 1] + sub
            )
    return dist[n][m]


# Combinaciones relación(acción) canónicas que el sintetizador produce.
_ACTION_COMBOS: tuple[tuple[str, str], ...] = (
    ("DESEAR", "COMUNICAR"),
    ("PREGUNTAR", "SER"),
    ("NO_SER", "TEMER"),  # la transmisión: negación sobre el temor
)


def _match_packet(ratios: list[float]) -> dict:
    """Busca la mejor interpretación estructural de una secuencia de ratios."""
    best: dict = {"score": -1.0}
    candidates: list[tuple[Concept, Concept | None]] = []
    for relation in _candidate_relations():
        candidates.append((relation, None))
    for rel_name, act_name in _ACTION_COMBOS:
        candidates.append((resolve(rel_name), resolve(act_name)))

    for relation, action in candidates:
        for target_ratio in (None, 3 / 2, 5 / 4, 16 / 15):
            for open_cadence in (False, True):
                expected, units = _expected_sequence(relation, action, target_ratio, open_cadence)
                distance = _distance(ratios, expected)
                score = 1.0 - distance / max(len(ratios), len(expected))
                if score > best["score"]:
                    best = {
                        "score": score,
                        "relation": relation,
                        "action": action,
                        "target_ratio": target_ratio,
                        "open_cadence": open_cadence,
                        "expected_units": units,
                    }
    return best


# -- análisis espectral ligero -------------------------------------------------------

def _goertzel(chunk: list[float], sr: int, freq: float) -> float:
    w = 2 * math.pi * freq / sr
    coeff = 2 * math.cos(w)
    s1 = s2 = 0.0
    for v in chunk:
        s0 = v + coeff * s1 - s2
        s2, s1 = s1, s0
    return math.sqrt(max(0.0, s1 * s1 + s2 * s2 - coeff * s1 * s2))


def _brightness(samples: list[float], sr: int, tones: list[tuple[float, float, int]]) -> float:
    """Energía del 2º armónico relativa al fundamental, en el tono más largo."""
    if not tones:
        return 0.0
    f0, duration, position = max(tones, key=lambda t: t[1])
    start = position + int(0.1 * duration * sr)
    chunk = samples[start : start + min(4096, int(duration * sr * 0.8))]
    if len(chunk) < 512:
        return 0.0
    fundamental = _goertzel(chunk, sr, f0)
    if fundamental < 1e-9:
        return 0.0
    return _goertzel(chunk, sr, 2 * f0) / fundamental


# -- reconstrucción del paquete -------------------------------------------------------

def _rebuild_symbol(
    packet_events: list[tuple[float | None, float, int]],
    base: float,
    samples: list[float],
    sr: int,
) -> Symbol:
    tones = [(f, d, s) for f, d, s in packet_events if f is not None]
    # secuencia observada: ratios de los tonos + marcadores de silencio interno
    ratios: list[float] = []
    seen_tone = False
    for f, d, _s in packet_events:
        if f is not None:
            ratios.append(_quantize(f, base)[0])
            seen_tone = True
        elif seen_tone and d >= _MEANING_SILENCE:
            ratios.append(0.0)
    while ratios and ratios[-1] == 0.0:
        ratios.pop()  # el silencio final no significa: es el fin del paquete
    match = _match_packet(ratios)

    target_ratio = match["target_ratio"]
    dissonant = any(abs(r - 16 / 15) < 1e-9 for r in ratios)
    brightness = _brightness(samples, sr, tones)
    # pico de amplitud dentro del rango del paquete (no de todo el archivo)
    first, last = tones[0], tones[-1]
    packet_span = samples[first[2] : last[2] + int(last[1] * sr)]
    peak = max((abs(s) for s in packet_span), default=0.0)

    # valencia: la disonancia es negativa salvo que el destino sea consonante
    # (tensión que se resuelve hacia el vínculo: contenido temido, mensaje
    # protector — p. ej. «no temas lo desconocido»); brillo del timbre → positiva
    if dissonant and target_ratio == 3 / 2:
        valence = 0.3
    elif dissonant:
        valence = -0.7
    elif brightness > 0.16:
        valence = 0.6
    elif target_ratio == 3 / 2:
        valence = 0.4
    else:
        valence = 0.0

    bond = {3 / 2: 0.6, 5 / 4: 0.2, 16 / 15: -0.5}.get(target_ratio, 0.0)

    # urgencia: invierte la fórmula del tamaño de unidad del sintetizador
    total_tone = sum(d for _, d, _ in tones)
    unit = total_tone / match["expected_units"] if match["expected_units"] else 0.42
    urgency = ((0.42 * (1 + 0.35 * max(bond, 0.0)) / unit) - 1) / 0.9 if unit > 0 else 0.0
    urgency = max(0.0, min(1.0, urgency))

    arousal = max(0.0, min(1.0, ((peak / (1.3 if dissonant else 1.15)) - 0.28) / 0.35))
    certainty = -0.4 if match["open_cadence"] else max(0.0, min(0.8, match["score"]))

    target = None
    if target_ratio is not None:
        target = P.OTRO if target_ratio == 3 / 2 else P.DESCONOCIDO

    return Symbol(
        source=P.YO,
        relation=match["relation"],
        action=match["action"],
        target=target,
        emotion=Emotion(
            valence=valence, arousal=arousal, certainty=certainty,
            urgency=urgency, bond=bond,
        ),
        meta={
            "listen": {
                "score": round(match["score"], 3),
                "base_hz": round(base, 2),
                "ratios": [round(r, 4) for r in ratios],
                "brightness": round(brightness, 3),
            }
        },
    )


def listen(path: str) -> Message:
    """Interpreta un WAV generado por WSP y reconstruye el mensaje simbólico."""
    samples, sr = read_wav(path)
    events = _tone_events(samples, sr)
    base = _estimate_base(events)
    if base is None:
        return Message(packets=[])

    # separa paquetes por silencios largos
    packets: list[list[tuple[float | None, float, int]]] = [[]]
    for f, d, s in events:
        if f is None and d >= _PACKET_SILENCE and packets[-1]:
            packets.append([])
        else:
            packets[-1].append((f, d, s))
    packets = [p for p in packets if any(f is not None for f, _, _ in p)]

    return Message(
        packets=[_rebuild_symbol(p, base, samples, sr) for p in packets]
    )
