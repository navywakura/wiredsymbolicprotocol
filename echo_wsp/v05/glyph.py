"""Renderizador visual: símbolo → glifo SVG.

Los glifos nacen de la geometría, no de letras (Fase 5):

    punto          = ser                línea    = relación
    círculo        = campo / mundo      flecha   = dirección / deseo
    onda           = información        ruptura  = negación / separación
    doble círculo  = conciencia         espiral  = generatividad / creación
    zigzag         = tensión / peligro  eco      = memoria / repetición

La emoción se expresa como estilo: color = valencia, grosor = activación,
trazo discontinuo = duda, púas radiales = urgencia, campo envolvente = vínculo.
"""

from __future__ import annotations

import math

from .concepts import Derived, concept_name
from .primitives import Primitive
from .symbol import Message, Symbol

ROW_W = 420
ROW_H = 240


def _color(valence: float) -> str:
    if valence >= 0.25:
        return "#2e9e6b"
    if valence <= -0.25:
        return "#c0392b"
    return "#8a8f98"


def _entity_glyph(x: float, y: float, concept, color: str) -> list[str]:
    """Dibuja una entidad: punto = ser, círculo = campo, satélites = composición."""
    name = concept_name(concept)
    parts: list[str] = []
    if name == "YO":
        # ser dentro de su mundo: punto lleno dentro de círculo
        parts.append(f'<circle cx="{x}" cy="{y}" r="20" fill="none" stroke="{color}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}"/>')
    elif name == "OTRO":
        # el otro: presencia aún no integrada (punto hueco)
        parts.append(f'<circle cx="{x}" cy="{y}" r="20" fill="none" stroke="{color}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="none" stroke="{color}" stroke-width="2"/>')
    elif name == "NO_SER":
        parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<line x1="{x-12}" y1="{y+12}" x2="{x+12}" y2="{y-12}" stroke="{color}" stroke-width="2"/>')
    elif name == "DESCONOCIDO":
        parts.append(f'<circle cx="{x}" cy="{y}" r="9" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="3 4"/>')
    elif isinstance(concept, Derived):
        # concepto compuesto: núcleo + un satélite por átomo componente
        parts.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}"/>')
        n = len(concept.components)
        for i in range(n):
            angle = -math.pi / 2 + 2 * math.pi * i / n
            sx = x + 16 * math.cos(angle)
            sy = y + 16 * math.sin(angle)
            parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="2.5" fill="{color}"/>')
    else:
        parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{color}"/>')
    return parts


def _wave_path(x1: float, x2: float, y: float, amp: float = 12.0, wavelength: float = 34.0) -> str:
    points = []
    x = x1
    while x <= x2:
        points.append(f"{x:.1f},{y + amp * math.sin(2 * math.pi * (x - x1) / wavelength):.1f}")
        x += 4
    return f'<polyline points="{" ".join(points)}" fill="none"'


def _zigzag_path(x1: float, x2: float, y: float, amp: float = 12.0, step: float = 14.0) -> str:
    points = [f"{x1:.1f},{y:.1f}"]
    x = x1 + step
    up = True
    while x < x2:
        points.append(f"{x:.1f},{y + (-amp if up else amp):.1f}")
        up = not up
        x += step
    points.append(f"{x2:.1f},{y:.1f}")
    return f'<polyline points="{" ".join(points)}" fill="none"'


def _spiral(x: float, y: float, color: str, width: float) -> str:
    points = []
    theta = 0.0
    while theta <= 3.5 * math.pi:
        r = 2.0 + 2.2 * theta
        points.append(f"{x + r * math.cos(theta):.1f},{y + r * math.sin(theta):.1f}")
        theta += 0.25
    return (
        f'<polyline points="{" ".join(points)}" fill="none" '
        f'stroke="{color}" stroke-width="{width}"/>'
    )


def _relation_path(symbol: Symbol, x1: float, x2: float, y: float, color: str, width: float, dash: str) -> list[str]:
    relation = concept_name(symbol.relation) or ""
    stroke = f' stroke="{color}" stroke-width="{width}"{dash}/>'
    parts: list[str] = []

    if relation in ("SEPARAR", "NO_SER"):
        # ruptura: línea partida (negación / pérdida)
        mid = (x1 + x2) / 2
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{mid - 16}" y2="{y}"{stroke}')
        parts.append(f'<line x1="{mid + 16}" y1="{y}" x2="{x2}" y2="{y}"{stroke}')
    elif relation in ("TEMER",) or concept_name(symbol.target) == "PELIGRO":
        parts.append(_zigzag_path(x1, x2, y) + stroke)
    elif relation == "PREGUNTAR":
        # arco ascendente abierto (búsqueda) con final hueco
        parts.append(
            f'<path d="M {x1} {y} Q {(x1 + x2) / 2} {y - 46} {x2 - 8} {y - 18}" fill="none"{stroke}'
        )
        parts.append(f'<circle cx="{x2 - 4}" cy="{y - 20}" r="4" fill="none"{stroke}')
    elif relation == "DESEAR":
        # flecha: dirección hacia lo deseado
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2 - 10}" y2="{y}"{stroke}')
        parts.append(
            f'<polygon points="{x2},{y} {x2 - 14},{y - 7} {x2 - 14},{y + 7}" fill="{color}"/>'
        )
    elif relation in ("COMUNICAR", "RESPONDER", "OBSERVAR", "AMOR"):
        # onda: información/vínculo viajando entre seres
        # (AMOR = dos puntos unidos por onda dentro de un campo)
        parts.append(_wave_path(x1, x2, y) + stroke)
    elif relation == "RECORDAR":
        # eco: repetición = memoria
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"{stroke}')
        parts.append(f'<line x1="{x1 + 12}" y1="{y + 10}" x2="{x2 - 12}" y2="{y + 10}" stroke="{color}" stroke-width="{max(1.0, width - 1)}" opacity="0.45"{dash}/>')
    elif relation == "CREAR":
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"{stroke}')
        parts.append(_spiral((x1 + x2) / 2, y - 34, color, max(1.0, width - 1)))
    else:
        parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"{stroke}')

    # la acción anidada viaja como onda pequeña sobre la relación
    if symbol.action is not None and relation not in ("PREGUNTAR",):
        parts.append(
            _wave_path(x1 + 16, x2 - 16, y - 22, amp=6.0, wavelength=22.0)
            + f' stroke="{color}" stroke-width="{max(1.0, width - 1.2)}" opacity="0.6"/>'
        )
    return parts


def _render_row(symbol: Symbol, y0: float, labels: bool) -> list[str]:
    e = symbol.emotion
    color = _color(e.valence)
    width = 1.5 + 2.5 * max(e.arousal, 0.0)
    dash = ' stroke-dasharray="6 5"' if e.certainty < -0.2 else ""
    cy = y0 + 105
    sx, tx = 110, 310
    center = (sx + tx) / 2
    parts: list[str] = []

    # la Wired: retícula de fondo (la red dentro de la cual todo se conecta)
    if concept_name(symbol.space) == "WIRED":
        for gx in range(40, ROW_W - 20, 34):
            parts.append(
                f'<line x1="{gx}" y1="{y0 + 18}" x2="{gx}" y2="{y0 + ROW_H - 46}" stroke="#b03030" stroke-width="0.6" opacity="0.18"/>'
            )
        for gy in range(int(y0) + 26, int(y0) + ROW_H - 46, 30):
            parts.append(
                f'<line x1="34" y1="{gy}" x2="{ROW_W - 30}" y2="{gy}" stroke="#b03030" stroke-width="0.6" opacity="0.18"/>'
            )

    # vínculo: campo envolvente que contiene a ambos seres
    if e.bond > 0.4:
        parts.append(
            f'<ellipse cx="{center}" cy="{cy}" rx="155" ry="78" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.4"/>'
        )
    # espacio DENTRO: contenedor explícito
    if concept_name(symbol.space) == "DENTRO":
        parts.append(
            f'<ellipse cx="{center}" cy="{cy}" rx="165" ry="86" fill="none" stroke="#8a8f98" stroke-width="1" stroke-dasharray="4 5" opacity="0.6"/>'
        )

    has_target = symbol.target is not None
    if symbol.source is not None:
        parts += _entity_glyph(sx, cy, symbol.source, color)
    if has_target:
        parts += _entity_glyph(tx, cy, symbol.target, color)

    x1 = sx + 26
    x2 = tx - 26 if has_target else sx + 150
    if symbol.relation is not None:
        parts += _relation_path(symbol, x1, x2, cy, color, width, dash)

    # urgencia: púas radiales alrededor del destino (o del origen si no hay destino)
    if e.urgency > 0.5:
        ux = tx if has_target else sx
        for i in range(8):
            angle = 2 * math.pi * i / 8
            r1, r2 = 26, 26 + 8 + 8 * e.urgency
            parts.append(
                f'<line x1="{ux + r1 * math.cos(angle):.1f}" y1="{cy + r1 * math.sin(angle):.1f}" '
                f'x2="{ux + r2 * math.cos(angle):.1f}" y2="{cy + r2 * math.sin(angle):.1f}" '
                f'stroke="{color}" stroke-width="1.5"/>'
            )

    # marca temporal: antes / ahora / después sobre una línea de tiempo
    time = concept_name(symbol.time)
    if time in ("ANTES", "AHORA", "DESPUES"):
        ty = y0 + ROW_H - 36
        parts.append(f'<line x1="{center - 34}" y1="{ty}" x2="{center + 34}" y2="{ty}" stroke="#8a8f98" stroke-width="1"/>')
        tx_mark = {"ANTES": center - 26, "AHORA": center, "DESPUES": center + 26}[time]
        parts.append(f'<circle cx="{tx_mark}" cy="{ty}" r="3.5" fill="#8a8f98"/>')

    if labels:
        gloss = f'{symbol.compact().split(" | ")[0]} · {e.describe("es")}'
        # comprime la glosa si excede el ancho del lienzo (~6 px por carácter)
        fit = f' textLength="{ROW_W - 36}" lengthAdjust="spacingAndGlyphs"' if len(gloss) * 6 > ROW_W - 36 else ""
        parts.append(
            f'<text x="{ROW_W / 2}" y="{y0 + ROW_H - 12}" text-anchor="middle" '
            f'font-family="monospace" font-size="10" fill="#667"{fit}>{gloss}</text>'
        )
    return parts


def render_svg(message: Message | Symbol, labels: bool = True) -> str:
    """Convierte un mensaje simbólico en un glifo SVG (una fila por paquete)."""
    packets = message.packets if isinstance(message, Message) else [message]
    packets = packets or [Symbol()]
    height = ROW_H * len(packets)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ROW_W}" height="{height}" '
        f'viewBox="0 0 {ROW_W} {height}">'
    ]
    for i, symbol in enumerate(packets):
        parts += _render_row(symbol, i * ROW_H, labels)
    parts.append("</svg>")
    return "\n".join(parts)


def render_svg_file(message: Message | Symbol, path: str, labels: bool = True) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_svg(message, labels=labels))
    return path
