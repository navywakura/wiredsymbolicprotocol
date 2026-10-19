"""Parser de la forma compacta (v0.2): otra máscara que vuelve al símbolo.

    YO → DESEAR(COMUNICAR) → OTRO @AHORA @WIRED | E[V+0.70 A+0.40 ... B+0.80]

Acepta también la flecha ASCII "->" y la parte emocional es opcional.
"""

from __future__ import annotations

import re

from .concepts import resolve
from .emotion import AXIS_LETTERS, Emotion
from .primitives import Category
from .symbol import Message, Symbol

_EMO_RE = re.compile(r"E\[([^\]]*)\]")
_AXIS_RE = re.compile(r"([VADCUB])([+-]\d+(?:\.\d+)?)")
_REL_RE = re.compile(r"^([^()\s]+)(?:\(([^()\s]+)\))?$")


def parse_compact(line: str) -> Symbol:
    """Convierte una línea en forma compacta en un paquete simbólico."""
    line = line.strip().replace("->", "→")
    if not line:
        raise ValueError("línea compacta vacía")

    # separa estructura y emoción
    emotion = Emotion()
    if "|" in line:
        structure, _, tail = line.partition("|")
        match = _EMO_RE.search(tail)
        if match:
            letters = {v: k for k, v in AXIS_LETTERS.items()}
            values = {
                letters[axis]: float(value) for axis, value in _AXIS_RE.findall(match.group(1))
            }
            emotion = Emotion(**values)
    else:
        structure = line

    # extrae marcadores @TIEMPO / @ESPACIO
    time = space = None
    tokens = []
    for token in structure.split():
        if token.startswith("@"):
            concept = resolve(token[1:])
            category = getattr(concept, "category", None)
            if category == Category.TIME:
                time = concept
            else:
                space = concept
        elif token:
            tokens.append(token)

    # estructura: ORIGEN → RELACIÓN(ACCIÓN) [→ DESTINO]
    parts = [t for t in " ".join(tokens).split("→") if t.strip()]
    if not parts:
        raise ValueError(f"forma compacta sin estructura: {line!r}")

    def _concept(text: str):
        text = text.strip()
        return None if text in ("∅", "") else resolve(text)

    source = _concept(parts[0])
    relation = action = target = None
    if len(parts) > 1:
        match = _REL_RE.match(parts[1].strip())
        if not match:
            raise ValueError(f"relación ilegible: {parts[1]!r}")
        relation = _concept(match.group(1))
        if match.group(2):
            action = _concept(match.group(2))
    if len(parts) > 2:
        target = _concept(parts[2])

    return Symbol(
        source=source, relation=relation, action=action, target=target,
        time=time, space=space, emotion=emotion,
    )


def parse_compact_message(text: str) -> Message:
    """Una línea por paquete; ignora líneas vacías."""
    packets = [parse_compact(line) for line in text.splitlines() if line.strip()]
    return Message(packets=packets)
