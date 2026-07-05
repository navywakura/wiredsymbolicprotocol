"""Capa E de ROGEX-WSP: la emoción como carga de importancia.

Seis ejes continuos en [-1.0, +1.0] (Fase 2 del protocolo):

    V = valencia:   negativo  <-> positivo
    A = activación: calma     <-> intensidad
    D = dominancia: sometido  <-> control
    C = certeza:    duda      <-> seguridad
    U = urgencia:   lento     <-> inmediato
    B = vínculo:    distancia <-> cercanía
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

AXES: tuple[str, ...] = ("valence", "arousal", "dominance", "certainty", "urgency", "bond")

AXIS_LETTERS: dict[str, str] = {
    "valence": "V",
    "arousal": "A",
    "dominance": "D",
    "certainty": "C",
    "urgency": "U",
    "bond": "B",
}

_DESCRIPTORS = {
    "es": {
        "valence": ("negativo", "positivo"),
        "arousal": ("calmado", "intenso"),
        "dominance": ("sometido", "dominante"),
        "certainty": ("incierto", "seguro"),
        "urgency": ("pausado", "urgente"),
        "bond": ("distante", "cercano"),
    },
    "en": {
        "valence": ("negative", "positive"),
        "arousal": ("calm", "intense"),
        "dominance": ("yielding", "dominant"),
        "certainty": ("uncertain", "certain"),
        "urgency": ("slow", "urgent"),
        "bond": ("distant", "close"),
    },
}


def _clamp(v: float) -> float:
    return max(-1.0, min(1.0, float(v)))


@dataclass(frozen=True)
class Emotion:
    """Firma emocional de un símbolo. Todos los ejes viven en [-1, +1]."""

    valence: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0
    certainty: float = 0.0
    urgency: float = 0.0
    bond: float = 0.0

    def __post_init__(self) -> None:
        for axis in AXES:
            object.__setattr__(self, axis, _clamp(getattr(self, axis)))

    # -- serialización ---------------------------------------------------
    def to_dict(self) -> dict[str, float]:
        return {axis: round(getattr(self, axis), 4) for axis in AXES}

    @classmethod
    def from_dict(cls, data: dict) -> "Emotion":
        """Acepta claves largas ("valence") o cortas ("V"), sin distinguir mayúsculas."""
        letters = {letter.lower(): axis for axis, letter in AXIS_LETTERS.items()}
        values: dict[str, float] = {}
        for key, value in (data or {}).items():
            axis = key.lower()
            axis = letters.get(axis, axis)
            if axis in AXES:
                values[axis] = float(value)
        return cls(**values)

    # -- operaciones ------------------------------------------------------
    def replace(self, **changes: float) -> "Emotion":
        return dataclasses.replace(self, **changes)

    def shift(self, **deltas: float) -> "Emotion":
        """Desplaza ejes de forma aditiva (con clamp automático)."""
        values = {axis: getattr(self, axis) + deltas.get(axis, 0.0) for axis in AXES}
        return Emotion(**values)

    def blend(self, other: "Emotion", weight: float = 0.5) -> "Emotion":
        """Mezcla lineal entre dos firmas emocionales."""
        w = _clamp(weight) if weight >= 0 else 0.0
        values = {
            axis: getattr(self, axis) * (1 - w) + getattr(other, axis) * w for axis in AXES
        }
        return Emotion(**values)

    def is_neutral(self, threshold: float = 0.1) -> bool:
        return all(abs(getattr(self, axis)) < threshold for axis in AXES)

    # -- render ------------------------------------------------------------
    def signature(self) -> str:
        """Forma compacta legible por máquina: 'V+0.95 A+0.60 ... B+0.98'."""
        return " ".join(
            f"{AXIS_LETTERS[axis]}{getattr(self, axis):+.2f}" for axis in AXES
        )

    def describe(self, lang: str = "es", threshold: float = 0.3) -> str:
        """Descripción humana: 'positivo, intenso, cercano'."""
        words = []
        table = _DESCRIPTORS.get(lang, _DESCRIPTORS["es"])
        for axis in AXES:
            value = getattr(self, axis)
            if abs(value) >= threshold:
                words.append(table[axis][1 if value > 0 else 0])
        if not words:
            return "neutro" if lang == "es" else "neutral"
        return ", ".join(words)
