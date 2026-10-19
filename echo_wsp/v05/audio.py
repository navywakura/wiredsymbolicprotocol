"""Renderizador sonoro: símbolo → eventos acústicos (WAV).

No hay palabras habladas. El significado se codifica en relaciones de
frecuencia (ratios, no Hz absolutos) y la emoción en parámetros musicales:

    ratio 1:1   = identidad / ser          tempo    = urgencia
    ratio 3:2   = conexión / relación      volumen  = intensidad (activación)
    ratio 5:4   = armonía / afinidad       brillo   = valencia
    ratio 4:3   = estabilidad              vibrato  = duda (certeza baja)
    ratio 9:8   = movimiento / tensión     duración = importancia / vínculo
    ratio 16:15 = tensión / disonancia     silencio = ausencia / negación
    ascendente  = apertura / pregunta      descendente = cierre / afirmación
"""

from __future__ import annotations

import math
import struct
import wave

from .concepts import Concept, Derived, concept_name
from .primitives import Primitive
from .symbol import Message, Symbol

SAMPLE_RATE = 22050
BASE_FREQ = 220.0

# v0.3 target burst: short microtonal symbols around the calibrated base.
_BURST_TONE = 0.036
_BURST_GAP = 0.008
_BURST_LEAD = 0.080
_BURST_PREAMBLE = (2.0, 0.5)


def _target_bytes(symbol: Symbol) -> bytes:
    """Stable compact identity payload for a non-generic target."""
    if symbol.target is None:
        return b""
    name = concept_name(symbol.target)
    if name in ("OTRO", "DESCONOCIDO"):
        return b""
    return name.encode("utf-8")[:24]


def _nibble_ratio(value: int) -> float:
    """Map a nibble to a microtonal ratio spanning roughly a tritone."""
    return 2.0 ** ((value - 7.5) / 24.0)


def _burst_ratios(payload: bytes) -> list[float]:
    ratios = list(_BURST_PREAMBLE)
    ratios.append(_nibble_ratio(len(payload) & 0x0F))
    for byte in payload:
        ratios.extend((_nibble_ratio(byte >> 4), _nibble_ratio(byte & 0x0F)))
    checksum = sum(payload) & 0xFF
    ratios.extend((_nibble_ratio(checksum >> 4), _nibble_ratio(checksum & 0x0F)))
    return ratios

# Eventos por relación: (ratio, duración en unidades, pausa en unidades).
# ratio 0.0 = silencio (ausencia).
_RELATION_EVENTS: dict[str, list[tuple[float, float, float]]] = {
    "SER": [(1.0, 1.6, 0.1)],
    "NO_SER": [(1.0, 0.3, 0.05), (0.0, 0.9, 0.0)],
    "YO": [(1.0, 0.8, 0.1)],
    "OTRO": [(9 / 8, 0.8, 0.1)],
    "UNIR": [(3 / 2, 1.0, 0.1)],
    "SEPARAR": [(3 / 2, 0.4, 0.35), (1.0, 0.4, 0.1)],
    "CAMBIAR": [(1.0, 0.35, 0.05), (9 / 8, 0.35, 0.05), (5 / 4, 0.4, 0.1)],
    "OBSERVAR": [(4 / 3, 1.2, 0.1)],
    "PREGUNTAR": [(9 / 8, 0.4, 0.05), (4 / 3, 0.7, 0.3)],
    "RESPONDER": [(4 / 3, 0.4, 0.05), (1.0, 0.8, 0.2)],
    "DESEAR": [(5 / 4, 0.5, 0.05), (3 / 2, 0.8, 0.15)],
    "TEMER": [(16 / 15, 0.45, 0.1), (16 / 15, 0.45, 0.3)],
    "RECORDAR": [(1.0, 0.4, 0.15), (1.0, 0.4, 0.3)],
    "OLVIDAR": [(1.0, 0.6, 0.0), (0.0, 0.8, 0.0)],
    "CREAR": [(1.0, 0.3, 0.03), (5 / 4, 0.3, 0.03), (3 / 2, 0.5, 0.1)],
    "DESTRUIR": [(3 / 2, 0.3, 0.03), (5 / 4, 0.3, 0.03), (16 / 15, 0.5, 0.1)],
    "SUBIR": [(1.0, 0.35, 0.03), (9 / 8, 0.35, 0.03), (5 / 4, 0.4, 0.1)],
    "BAJAR": [(5 / 4, 0.35, 0.03), (9 / 8, 0.35, 0.03), (1.0, 0.4, 0.1)],
    "ABRIR": [(1.0, 0.35, 0.05), (4 / 3, 0.7, 0.1)],
    "CERRAR": [(4 / 3, 0.35, 0.05), (1.0, 0.7, 0.1)],
    "CAUSA": [(1.0, 0.4, 0.05), (3 / 2, 0.5, 0.1)],
    "EFECTO": [(3 / 2, 0.4, 0.05), (1.0, 0.5, 0.1)],
    "POSIBLE": [(5 / 4, 0.6, 0.1)],
    "IMPOSIBLE": [(16 / 15, 0.4, 0.05), (0.0, 0.5, 0.0)],
    "DESCONOCIDO": [(9 / 8, 0.5, 0.4)],
    "AQUI": [(1.0, 0.4, 0.05)],
    "ALLI": [(2.0, 0.4, 0.05)],
    "DENTRO": [(1 / 2, 0.4, 0.05)],
    "FUERA": [(2.0, 0.4, 0.05)],
    "AHORA": [(1.0, 0.3, 0.05)],
    "ANTES": [(8 / 9, 0.3, 0.05)],
    "DESPUES": [(9 / 8, 0.3, 0.05)],
}


def _events_for_concept(concept: Concept, scale: float = 1.0) -> list[tuple[float, float, float]]:
    name = concept_name(concept)
    if name in _RELATION_EVENTS:
        events = _RELATION_EVENTS[name]
    elif isinstance(concept, Derived):
        # Concepto derivado: la secuencia de sus átomos, comprimida.
        events = []
        for atom in concept.components:
            events += _events_for_concept(atom, scale=0.55)
        return [(r, d * scale, g * scale) for r, d, g in events]
    else:
        events = [(1.0, 0.5, 0.1)]
    return [(r, d * scale, g * scale) for r, d, g in events]


def _symbol_events(symbol: Symbol) -> list[tuple[float, float, float]]:
    e = symbol.emotion
    events: list[tuple[float, float, float]] = []

    # Pulso de identidad del origen.
    source = concept_name(symbol.source)
    source_ratio = 9 / 8 if source == "OTRO" else 1.0
    events.append((source_ratio, 0.5, 0.15))

    if symbol.relation is not None:
        events += _events_for_concept(symbol.relation)
    if symbol.action is not None:
        events += _events_for_concept(symbol.action, scale=0.7)

    # Pulso del destino: consonante si hay vínculo, disonante si es negativo.
    if symbol.target is not None:
        if e.bond > 0.3:
            target_ratio = 3 / 2
        elif e.valence < -0.3:
            target_ratio = 16 / 15
        else:
            target_ratio = 5 / 4
        events.append((target_ratio, 0.6, 0.1))

    # Cadencia: apertura ascendente (pregunta / duda) o cierre descendente.
    if concept_name(symbol.relation) == "PREGUNTAR" or e.certainty < -0.2:
        events += [(4 / 3, 0.3, 0.02), (3 / 2, 0.5, 0.0)]
    else:
        events.append((1.0, 0.8 if e.certainty > 0.5 else 0.5, 0.0))

    return events


def _tone(
    samples: list[float],
    freq: float,
    duration: float,
    amplitude: float,
    attack: float,
    vibrato_depth: float,
    harmonics: list[tuple[float, float]],
    sr: int,
) -> None:
    n = int(duration * sr)
    release = max(0.03, duration * 0.25)
    for i in range(n):
        t = i / sr
        vibrato = 1.0 + vibrato_depth * math.sin(2 * math.pi * 5.5 * t)
        phase = 2 * math.pi * freq * vibrato * t
        value = sum(a * math.sin(phase * mult) for mult, a in harmonics)
        if t < attack:
            env = t / attack
        elif t > duration - release:
            env = max(0.0, (duration - t) / release)
        else:
            env = 1.0
        samples.append(value * amplitude * env)


def _silence(samples: list[float], duration: float, sr: int) -> None:
    samples.extend(0.0 for _ in range(int(duration * sr)))


def synthesize(
    message: Message | Symbol,
    base_freq: float = BASE_FREQ,
    sr: int = SAMPLE_RATE,
) -> list[float]:
    """Sintetiza el mensaje como lista de muestras en [-1, 1]."""
    packets = message.packets if isinstance(message, Message) else [message]
    samples: list[float] = []

    for index, symbol in enumerate(packets):
        if index > 0:
            # separador de paquetes: más largo que cualquier silencio interno
            # con significado (negación/olvido), para que el receptor los distinga
            _silence(samples, 0.7, sr)
        e = symbol.emotion

        unit = 0.42 * (1.0 + 0.35 * max(e.bond, 0.0)) / (1.0 + 0.9 * max(e.urgency, 0.0))
        amplitude = 0.28 + 0.35 * max(e.arousal, 0.0)
        attack = 0.005 if (e.urgency > 0.6 or e.valence < -0.6) else 0.03 + 0.07 * max(e.bond, 0.0)
        vibrato_depth = 0.002 + 0.015 * max(0.0, -e.certainty)
        harmonics = [(1.0, 1.0), (2.0, 0.10 + 0.20 * max(e.valence, 0.0)), (3.0, 0.05)]
        dissonance = 0.30 * max(0.0, -e.valence)
        if dissonance > 0.0:
            harmonics.append((16 / 15, dissonance))

        for ratio, dur_units, gap_units in _symbol_events(symbol):
            duration = max(0.08, dur_units * unit)
            if ratio <= 0.0:
                _silence(samples, duration, sr)
            else:
                _tone(
                    samples, base_freq * ratio, duration, amplitude,
                    attack, vibrato_depth, harmonics, sr,
                )
            if gap_units > 0:
                _silence(samples, gap_units * unit, sr)

        payload = _target_bytes(symbol)
        if payload:
            _silence(samples, _BURST_LEAD, sr)
            for ratio in _burst_ratios(payload):
                _tone(
                    samples, base_freq * ratio, _BURST_TONE, amplitude * 0.78,
                    0.002, 0.0, [(1.0, 1.0)], sr,
                )
                _silence(samples, _BURST_GAP, sr)

    # Normaliza el pico para evitar clipping.
    peak = max((abs(s) for s in samples), default=1.0)
    if peak > 0.85:
        samples = [s * 0.85 / peak for s in samples]
    return samples


def render_wav(
    message: Message | Symbol,
    path: str,
    base_freq: float = BASE_FREQ,
    sr: int = SAMPLE_RATE,
) -> str:
    """Escribe el mensaje como archivo WAV (mono, 16 bits). Devuelve la ruta."""
    samples = synthesize(message, base_freq=base_freq, sr=sr)
    frames = b"".join(struct.pack("<h", int(s * 32767)) for s in samples)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(frames)
    return path
