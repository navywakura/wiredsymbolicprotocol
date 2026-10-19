"""Intérprete visual (v0.2 «Signal Return»): glifo SVG → símbolo.

Los glifos de WSP son XML estructurado, así que el camino de vuelta es
legible con `xml.etree`. Dos fuentes de verdad, en orden:

    1. la etiqueta de glosa (si el glifo se generó con labels=True):
       estructura exacta vía el parser de forma compacta
    2. la geometría: forma del trazo → relación, color → valencia,
       grosor → activación, discontinuo → duda, campo → vínculo,
       púas → urgencia, retícula → la Wired, punto temporal → tiempo

La geometría refina siempre la emoción; la etiqueta, cuando existe,
fija la estructura. Sin etiqueta, la relación se infiere de la forma
(onda, flecha, ruptura, arco, zigzag, espiral, eco, línea) con menos
certeza.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .compact import parse_compact
from .concepts import resolve
from .emotion import AXES, Emotion
from .glyph import ROW_H
from .primitives import Primitive
from .symbol import Message, Symbol

P = Primitive

# palabra de la glosa emocional → (eje, valor)
_WORD_AXES: dict[str, tuple[str, float]] = {
    "negativo": ("valence", -0.5), "positivo": ("valence", 0.5),
    "calmado": ("arousal", -0.5), "intenso": ("arousal", 0.5),
    "sometido": ("dominance", -0.5), "dominante": ("dominance", 0.5),
    "incierto": ("certainty", -0.5), "seguro": ("certainty", 0.5),
    "pausado": ("urgency", -0.5), "urgente": ("urgency", 0.5),
    "distante": ("bond", -0.5), "cercano": ("bond", 0.5),
}

_COLOR_VALENCE = {"#2e9e6b": 0.5, "#c0392b": -0.5, "#8a8f98": 0.0}


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _row_y(element: ET.Element) -> float | None:
    """Coordenada Y representativa de un elemento, para asignarlo a su fila."""
    for attr in ("cy", "y1", "y"):
        if attr in element.attrib:
            return float(element.attrib[attr])
    if "points" in element.attrib:
        first = element.attrib["points"].split()[0]
        return float(first.split(",")[1])
    if "d" in element.attrib:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", element.attrib["d"])
        if len(numbers) >= 2:
            return float(numbers[1])
    return None


def _points(element: ET.Element) -> list[tuple[float, float]]:
    pairs = []
    for token in element.attrib.get("points", "").split():
        x, y = token.split(",")
        pairs.append((float(x), float(y)))
    return pairs


def _classify_polyline(element: ET.Element) -> str:
    """onda | zigzag | espiral, según la trayectoria de los puntos."""
    points = _points(element)
    if len(points) < 3:
        return "linea"
    xs = [x for x, _ in points]
    monotonic = all(b >= a for a, b in zip(xs, xs[1:]))
    if not monotonic:
        return "espiral"
    ys = [y for _, y in points]
    crossings = 0
    mid = (max(ys) + min(ys)) / 2
    for a, b in zip(ys, ys[1:]):
        if (a - mid) * (b - mid) < 0:
            crossings += 1
    if len(points) > 14 and crossings >= 4:
        return "onda"
    return "zigzag"


def _shape_relation(shapes: dict) -> tuple[object, float]:
    """(relación inferida, certeza) a partir de la geometría, sin etiqueta."""
    if shapes.get("polygon"):
        return P.DESEAR, 0.5
    if shapes.get("arc"):
        return P.PREGUNTAR, 0.5
    if shapes.get("espiral"):
        return P.CREAR, 0.5
    if shapes.get("zigzag"):
        return P.TEMER, 0.5
    if shapes.get("broken_line"):
        return P.SEPARAR, 0.5
    if shapes.get("onda"):
        if shapes.get("bond_field") and shapes.get("valence", 0) > 0:
            return resolve("AMOR"), 0.4
        return resolve("COMUNICAR"), 0.4
    if shapes.get("echo"):
        return P.RECORDAR, 0.4
    if shapes.get("line"):
        return (P.UNIR, 0.4) if shapes.get("has_target") else (P.SER, 0.4)
    return P.DESCONOCIDO, 0.1


def _inspect_row(elements: list[ET.Element], y0: float) -> Symbol:
    shapes: dict = {}
    label_text = None
    stroke_widths: list[float] = []
    dashed = False
    horizontal_lines: list[tuple[float, float, float]] = []  # (x1, x2, y)
    diagonal_short = 0
    time_dot_x = None
    center = 210.0

    for el in elements:
        tag = _tag(el)
        stroke = el.attrib.get("stroke", "")
        width = float(el.attrib.get("stroke-width", 0) or 0)
        if stroke in _COLOR_VALENCE and _COLOR_VALENCE[stroke] != 0.0:
            shapes["valence"] = _COLOR_VALENCE[stroke]
        if el.attrib.get("fill", "") in _COLOR_VALENCE and _COLOR_VALENCE[el.attrib["fill"]] != 0.0:
            shapes.setdefault("valence", _COLOR_VALENCE[el.attrib["fill"]])
        if "stroke-dasharray" in el.attrib and tag not in ("ellipse",):
            dashed = True

        if tag == "text":
            label_text = "".join(el.itertext()).strip()
        elif tag == "ellipse" and float(el.attrib.get("rx", 0)) > 100:
            if "stroke-dasharray" not in el.attrib:
                shapes["bond_field"] = True
        elif tag == "polygon":
            shapes["polygon"] = True
        elif tag == "path":
            d = el.attrib.get("d", "")
            nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", d)]
            turns = 0
            if len(nums) >= 8:
                ys = nums[1::2]
                turns = sum((b-a)*(c-b) < 0 for a,b,c in zip(ys, ys[1:], ys[2:]))
            if "Q" in d or "C" in d:
                shapes["onda" if turns >= 3 else "arc"] = True
            elif turns >= 3:
                shapes["zigzag"] = True
            else:
                shapes["arc"] = True
            if width:
                stroke_widths.append(width)
        elif tag == "polyline":
            shapes[_classify_polyline(el)] = True
            if width:
                stroke_widths.append(width)
        elif tag == "circle":
            cx, r = float(el.attrib.get("cx", 0)), float(el.attrib.get("r", 0))
            fill = el.attrib.get("fill", "")
            if r == 3.5 and abs(float(el.attrib.get("cy", 0)) - (y0 + ROW_H - 36)) < 2:
                time_dot_x = cx
            elif cx > 260 and r >= 7:
                shapes["has_target"] = True
                if fill == "none":
                    shapes["target_hollow"] = True
            elif cx > 260 and r <= 3:
                shapes["target_satellites"] = shapes.get("target_satellites", 0) + 1
            elif cx < 160 and r >= 7:
                shapes["source_filled"] = fill != "none"
        elif tag == "line":
            if stroke == "#b03030":
                shapes["wired_grid"] = True
                continue
            x1, x2 = float(el.attrib.get("x1", 0)), float(el.attrib.get("x2", 0))
            ly1, ly2 = float(el.attrib.get("y1", 0)), float(el.attrib.get("y2", 0))
            if abs(ly1 - (y0 + ROW_H - 36)) < 3 and abs(ly1 - ly2) < 1:
                continue  # línea base del marcador temporal, no es relación
            if abs(ly1 - ly2) < 1 and abs(x2 - x1) > 30:
                horizontal_lines.append((min(x1, x2), max(x1, x2), ly1))
                if width:
                    stroke_widths.append(width)
            elif abs(x2 - x1) > 2 and abs(ly2 - ly1) > 2 and abs(x2 - x1) < 30:
                diagonal_short += 1

    # línea rota (dos tramos a la misma altura con hueco) o eco (dos alturas)
    if len(horizontal_lines) >= 2:
        ys = sorted(set(round(y) for _, _, y in horizontal_lines))
        if len(ys) == 1:
            shapes["broken_line"] = True
        else:
            shapes["echo"] = True
    elif len(horizontal_lines) == 1:
        shapes["line"] = True

    # -- estructura ------------------------------------------------------------
    label_used = False
    if label_text and "·" in label_text:
        structure_part, _, gloss_part = label_text.partition("·")
        try:
            symbol = parse_compact(structure_part.strip())
            label_used = True
        except (ValueError, KeyError):
            symbol = Symbol(source=P.YO)
        words = [w.strip() for w in gloss_part.split(",")]
    else:
        symbol = Symbol(source=P.YO)
        words = []

    if not label_used:
        relation, _rel_certainty = _shape_relation(shapes)
        symbol.relation = relation
        if shapes.get("has_target") and symbol.target is None:
            if shapes.get("target_satellites"):
                symbol.target = P.DESCONOCIDO  # compuesto: identidad no recuperable
            else:
                symbol.target = P.OTRO
        if shapes.get("wired_grid"):
            symbol.space = resolve("WIRED")
        if time_dot_x is not None:
            if time_dot_x < center - 10:
                symbol.time = P.ANTES
            elif time_dot_x > center + 10:
                symbol.time = P.DESPUES
            else:
                symbol.time = P.AHORA

    # -- emoción: glosa como base, geometría como refinamiento -------------------
    values = {axis: 0.0 for axis in AXES}
    for word in words:
        if word in _WORD_AXES:
            axis, value = _WORD_AXES[word]
            values[axis] = value
    if "valence" in shapes:
        values["valence"] = shapes["valence"] if values["valence"] == 0 else (
            abs(values["valence"]) * (1 if shapes["valence"] > 0 else -1)
        )
    if stroke_widths:
        values["arousal"] = max(
            values["arousal"], max(0.0, min(1.0, (max(stroke_widths) - 1.5) / 2.5))
        )
    if dashed:
        values["certainty"] = min(values["certainty"], -0.4)
    if shapes.get("bond_field"):
        values["bond"] = max(values["bond"], 0.6)
    if diagonal_short >= 4:
        values["urgency"] = max(values["urgency"], 0.7)
    if not label_used:
        values["certainty"] = min(values["certainty"], 0.4)

    symbol.emotion = Emotion(**values)
    symbol.meta = {
        "inspect": {
            "label_used": label_used,
            "shapes": sorted(k for k, v in shapes.items() if v is True),
        }
    }
    return symbol


def inspect_svg(source: str) -> Message:
    """Interpreta un glifo SVG generado por WSP (ruta de archivo o texto SVG)."""
    text = source
    if not source.lstrip().startswith("<"):
        with open(source, encoding="utf-8") as f:
            text = f.read()
    root = ET.fromstring(text)
    height = float(root.attrib.get("height", ROW_H))
    n_rows = max(1, round(height / ROW_H))

    rows: list[list[ET.Element]] = [[] for _ in range(n_rows)]
    for element in root.iter():
        if _tag(element) == "svg":
            continue
        y = _row_y(element)
        if y is None:
            continue
        index = min(n_rows - 1, max(0, int(y // ROW_H)))
        rows[index].append(element)

    packets = [_inspect_row(row, i * ROW_H) for i, row in enumerate(rows) if row]
    return Message(packets=packets)
