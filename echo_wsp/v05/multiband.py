"""Análisis multibanda (v0.3 «Third Kind»): audio externo → símbolo.

`listen.py` interpreta audio generado por el propio sintetizador WSP.
Este módulo da el primer paso hacia audio ajeno al protocolo: divide el
espectro en tres capas concurrentes y reconoce firmas de contacto cuyo
tono base es dinámico (la primera frecuencia detectada define el 1:1).

    Capa baja   (20–150 Hz)   contexto: tonos graves sostenidos anclan
                              el espacio-tiempo local (@AQUI)
    Capa media  (150–1200 Hz) melodía: los ratios de los átomos
    Capa alta   (>1200 Hz)    transitorios: flancos de sincronización

Los filtros son biquads Butterworth (RBJ audio cookbook) escritos a mano:
el núcleo del protocolo es stdlib pura, sin SciPy ni NumPy.

Los ratios se cuantizan con **plegado de octavas**: cada frecuencia se
reduce a su clase de tono en [1, 2) más un desplazamiento de octava.
Así 8:9 (segunda mayor descendente) y 4:9 (la misma nota una octava más
abajo) comparten clase 16:9 con octavas -1 y -2 — la octava es un canal
semántico propio (la caída al grave = anclaje de contexto).

Fixture normativa: el saludo de *Close Encounters* (RE–MI–DO–DO↓–SOL).
Sus cinco tonos se proyectan uno a uno sobre las cinco ranuras del
paquete WSP:

    RE  1:1        → origen   YO
    MI  9:8        → relación SER          (existencia, paso adelante)
    DO  16:9 (↓1)  → acción   BUSCAR      (tensión de búsqueda)
    DO  16:9 (↓2)  → espacio  @AQUI       (anclaje en la capa grave)
    SOL 4:3  (↓1)  → destino  CONEXION    (resolución abierta al vínculo)

    «Existo y busco un vínculo aquí.»
"""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, field

from .concepts import resolve
from .emotion import Emotion
from .listen import _f0_autocorr, _segments, read_wav
from .primitives import Primitive
from .symbol import Message, Symbol

P = Primitive

LOW_BAND = (20.0, 150.0)
MID_BAND = (150.0, 1200.0)
HIGH_CUT = 1200.0

# clases de tono conocidas dentro de [1, 2)
_PITCH_CLASSES: tuple[float, ...] = (
    1.0, 16 / 15, 9 / 8, 6 / 5, 5 / 4, 4 / 3, 3 / 2, 8 / 5, 5 / 3, 16 / 9, 15 / 8
)


# -- biquads Butterworth (RBJ audio cookbook), 2º orden ----------------------------

def _biquad(kind: str, fc: float, sr: int, q: float = 0.7071) -> tuple[float, ...]:
    w0 = 2 * math.pi * fc / sr
    cosw, sinw = math.cos(w0), math.sin(w0)
    alpha = sinw / (2 * q)
    if kind == "lowpass":
        b0 = b2 = (1 - cosw) / 2
        b1 = 1 - cosw
    else:  # highpass
        b0 = b2 = (1 + cosw) / 2
        b1 = -(1 + cosw)
        b2 = (1 + cosw) / 2
    a0 = 1 + alpha
    return (b0 / a0, b1 / a0, b2 / a0, (-2 * cosw) / a0, (1 - alpha) / a0)


def _apply_biquad(coeffs: tuple[float, ...], x: list[float]) -> list[float]:
    b0, b1, b2, a1, a2 = coeffs
    y = [0.0] * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        out = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, v
        y2, y1 = y1, out
        y[i] = out
    return y


def _bandpass(x: list[float], sr: int, lo: float, hi: float, passes: int = 2) -> list[float]:
    """Paso banda por cascada de biquads (passes=2 → 4º orden por lado)."""
    y = x
    for _ in range(passes):
        y = _apply_biquad(_biquad("highpass", lo, sr), y)
    for _ in range(passes):
        y = _apply_biquad(_biquad("lowpass", hi, sr), y)
    return y


def split_bands(samples: list[float], sr: int) -> dict[str, list[float]]:
    """Divide la señal en las tres capas espectrales del protocolo."""
    high = samples
    for _ in range(2):
        high = _apply_biquad(_biquad("highpass", HIGH_CUT, sr), high)
    return {
        "low": _bandpass(samples, sr, *LOW_BAND),
        "mid": _bandpass(samples, sr, *MID_BAND),
        "high": high,
    }


# -- seguimiento de tono por banda ---------------------------------------------------

def _track_tones(
    samples: list[float], sr: int, fmin: float, fmax: float
) -> list[tuple[float, float, float]]:
    """Tonos (frecuencia, duración s, inicio s) en una banda ya filtrada.

    Los tonos con energía muy inferior al más fuerte de la banda se
    descartan: son fugas de otra capa o ringing del propio filtro.
    """
    # la ventana debe abarcar ≥2 periodos de la frecuencia más grave rastreable
    win = max(int(2.2 * sr / fmin), int(sr * 0.04))
    hop = max(1, win // 3)
    tones: list[tuple[float, float, float, float]] = []  # (f, dur, t0, rms)
    for start, end, is_tone in _segments(samples, sr):
        if not is_tone:
            continue
        freqs: list[float] = []
        i = start
        while i + win <= end:
            f0 = _f0_autocorr(samples[i : i + win], sr, fmin=fmin, fmax=fmax)
            freqs.append(f0 if f0 else 0.0)
            i += hop
        if not freqs and end - start >= win // 2:
            f0 = _f0_autocorr(samples[start:end], sr, fmin=fmin, fmax=fmax)
            freqs = [f0 if f0 else 0.0]
        runs: list[tuple[int, list[float]]] = []
        for k, f in enumerate(freqs):
            if runs and runs[-1][1][-1] > 0 and f > 0 and abs(f - runs[-1][1][-1]) / runs[-1][1][-1] < 0.045:
                runs[-1][1].append(f)
            else:
                runs.append((k, [f]))
        for first, run in runs:
            valid = sorted(f for f in run if f > 0)
            duration = max(len(run) * hop, win) / sr
            if valid and duration >= 0.06:
                s0 = start + first * hop
                span = samples[s0 : s0 + int(duration * sr)]
                rms = math.sqrt(sum(v * v for v in span) / max(1, len(span)))
                tones.append((valid[len(valid) // 2], duration, s0 / sr, rms))
    if not tones:
        return []
    strongest = max(rms for _, _, _, rms in tones)
    return [(f, d, t) for f, d, t, rms in tones if rms >= 0.15 * strongest]


def _onsets(samples: list[float], sr: int) -> int:
    """Flancos de subida rápidos en la señal (capa alta: sincronización)."""
    hop = max(1, sr // 100)
    previous = 0.0
    count = 0
    peak = max((abs(s) for s in samples), default=0.0)
    threshold = max(1e-4, peak * 0.1)
    for i in range(0, len(samples) - hop, hop):
        chunk = samples[i : i + hop]
        rms = math.sqrt(sum(v * v for v in chunk) / len(chunk))
        if rms > threshold and rms > 3 * previous:
            count += 1
        previous = rms
    return count


# -- plegado de octavas ------------------------------------------------------------

def fold_ratio(freq: float, base: float) -> tuple[float, int, float]:
    """(clase de tono cuantizada en [1,2), octava, error relativo en log)."""
    ratio = freq / base
    octave = math.floor(math.log2(ratio))
    folded = ratio / (2 ** octave)
    best = min(_PITCH_CLASSES, key=lambda c: abs(math.log(folded / c)))
    # 2.0 pliega a 1.0 en la octava siguiente
    error = abs(math.log(folded / best))
    if abs(math.log(folded / 2.0)) < error:
        best, octave, error = 1.0, octave + 1, abs(math.log(folded / 2.0))
    return best, octave, error


@dataclass
class MultibandReport:
    """Las tres capas espectrales de una señal, ya interpretadas."""

    sr: int
    low_tones: list[tuple[float, float, float]] = field(default_factory=list)
    mid_tones: list[tuple[float, float, float]] = field(default_factory=list)
    high_onsets: int = 0

    def merged_tones(self) -> list[tuple[float, float, float]]:
        """Tonos de las capas baja y media, en orden temporal."""
        return sorted(self.low_tones + self.mid_tones, key=lambda t: t[2])


def _decimate(samples: list[float], sr: int, target_sr: float) -> tuple[list[float], int]:
    """Submuestrea una banda ya filtrada (el filtro actúa de antialias)."""
    factor = max(1, int(sr // target_sr))
    return samples[::factor], round(sr / factor)


def _drop_subharmonic_ghosts(
    low: list[tuple[float, float, float]], mid: list[tuple[float, float, float]]
) -> list[tuple[float, float, float]]:
    """Descarta tonos graves que son la sub-octava fantasma de un tono medio.

    La atenuación del filtro no es infinita: un tono medio se cuela débil en
    la capa grave y la autocorrelación (limitada a frecuencias graves) lo
    detecta a la mitad de su frecuencia. El fantasma coincide EN EL TIEMPO
    con su tono medio; un grave legítimo suena cuando la capa media calla.
    """
    clean = []
    for f_low, d_low, t_low in low:
        ghost = False
        for f_mid, d_mid, t_mid in mid:
            overlap = min(t_low + d_low, t_mid + d_mid) - max(t_low, t_mid)
            if overlap > 0.5 * d_low and abs(f_mid / (2 * f_low) - 1.0) < 0.05:
                ghost = True
                break
        if not ghost:
            clean.append((f_low, d_low, t_low))
    return clean


def analyze(source: str | list[float], sr: int | None = None) -> MultibandReport:
    """Analiza un WAV (ruta) o una lista de muestras por las tres capas."""
    if isinstance(source, str):
        samples, sr = read_wav(source)
    else:
        samples = source
        if sr is None:
            raise ValueError("se necesita sr al analizar muestras crudas")
    bands = split_bands(samples, sr)
    low_dec, low_sr = _decimate(bands["low"], sr, 2000.0)
    mid_dec, mid_sr = _decimate(bands["mid"], sr, 6300.0)
    low_tones = _track_tones(low_dec, low_sr, fmin=25.0, fmax=160.0)
    mid_tones = _track_tones(mid_dec, mid_sr, fmin=140.0, fmax=1250.0)
    return MultibandReport(
        sr=sr,
        low_tones=_drop_subharmonic_ghosts(low_tones, mid_tones),
        mid_tones=mid_tones,
        high_onsets=_onsets(bands["high"], sr),
    )


# -- el saludo de contacto (fixture normativa de la v0.3) ---------------------------

# contorno esperado: (clase de tono, octava) relativos al primer tono
_HANDSHAKE_CONTOUR: tuple[tuple[float, int], ...] = (
    (1.0, 0),        # RE  → YO
    (9 / 8, 0),      # MI  → SER
    (16 / 9, -1),    # DO  → BUSCAR
    (16 / 9, -2),    # DO↓ → @AQUI (anclaje grave)
    (4 / 3, -1),     # SOL → CONEXION (variante clásica, quinta sobre el DO grave)
)
_TOLERANCE = 0.035  # en log-ratio (~3.5 %)


def translate_alien_handshake(source: str | MultibandReport) -> Message | None:
    """Reconoce el saludo de cinco tonos y lo traduce a un paquete WSP.

    Acepta el tono base en cualquier frecuencia (f0 dinámico: el primer
    tono define el 1:1) y la variante con el SOL en la octava aguda.
    Devuelve None si la señal no lleva la firma.
    """
    report = analyze(source) if isinstance(source, str) else source
    tones = report.merged_tones()
    if len(tones) < 5:
        return None

    def _step_ok(freq: float, base: float, step: tuple[float, int]) -> float | None:
        """Error si el tono encaja en el paso del contorno; None si no."""
        expected_class, expected_octave = step
        pitch_class, octave, error = fold_ratio(freq, base)
        if abs(math.log(pitch_class / expected_class)) < 1e-9 and error < _TOLERANCE:
            if octave == expected_octave:
                return error
            # variante: el SOL final una octava arriba (cuarta justa sobre la base)
            if expected_class == 4 / 3 and octave in (-1, 0):
                return error
        return None

    def _match_from(start: int) -> list[float] | None:
        """Empareja el contorno como subsecuencia, saltando ≤2 tonos espurios."""
        base = tones[start][0]
        errors: list[float] = []
        idx, skips = start, 0
        for step in _HANDSHAKE_CONTOUR:
            while idx < len(tones):
                error = _step_ok(tones[idx][0], base, step)
                idx += 1
                if error is not None:
                    errors.append(error)
                    break
                skips += 1
                if skips > 2:
                    return None
            else:
                return None
        return errors

    for offset in range(len(tones) - 4):
        errors = _match_from(offset)
        if errors is None:
            continue

        base = tones[offset][0]
        mean_error = sum(errors) / len(errors)
        score = round(min(0.99, 0.95 + 0.04 * (1 - mean_error / _TOLERANCE)), 3)
        grounded_in_bass = any(
            abs(t[0] - base * 4 / 9) / (base * 4 / 9) < 0.05 for t in report.low_tones
        )
        symbol = Symbol(
            source=P.YO,
            relation=P.SER,
            action=resolve("BUSCAR"),
            target=resolve("CONEXION"),
            space=P.AQUI,
            time=P.AHORA,
            emotion=Emotion(valence=0.4, arousal=0.5, certainty=0.3, urgency=0.2, bond=0.8),
            meta={
                "contact": {
                    "score": score,
                    "base_hz": round(base, 2),
                    "contour": ["1/1", "9/8", "16/9↓1", "16/9↓2", "4/3↓1"],
                    "grounded_in_bass": grounded_in_bass,
                    "bands": {
                        "low_tones": len(report.low_tones),
                        "mid_tones": len(report.mid_tones),
                        "high_onsets": report.high_onsets,
                    },
                }
            },
        )
        return Message(packets=[symbol])
    return None


def emit_handshake(path: str, base: float = 293.66, sr: int = 44100) -> str:
    """Emite el saludo de cinco tonos como WAV (la respuesta de WSP al contacto).

    `base` es la frecuencia del primer tono (por defecto RE4, como en la película);
    el resto se deriva por ratios, nunca por notas absolutas.
    """
    ratios = (1.0, 9 / 8, 8 / 9, 4 / 9, 2 / 3)
    durations = (0.55, 0.55, 0.55, 0.55, 1.1)
    samples: list[float] = []
    for ratio, duration in zip(ratios, durations):
        freq = base * ratio
        n = int(duration * sr)
        attack = int(0.02 * sr)
        release = int(0.12 * sr)
        for i in range(n):
            t = i / sr
            value = math.sin(2 * math.pi * freq * t) + 0.15 * math.sin(4 * math.pi * freq * t)
            if i < attack:
                env = i / attack
            elif i > n - release:
                env = max(0.0, (n - i) / release)
            else:
                env = 1.0
            samples.append(0.5 * value * env)
        samples.extend(0.0 for _ in range(int(0.08 * sr)))
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(frames)
    return path
