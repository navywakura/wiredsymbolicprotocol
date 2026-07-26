"""Sintaxis agnóstica (v0.5): campos etiquetados, orden libre.

La gramática de WSP hasta la v0.4 era posicional:

    [ORIGEN] [RELACIÓN(ACCIÓN)] [DESTINO] @TIEMPO @ESPACIO

Eso presupone que el emisor ordena el mundo como nosotros. Una especie
cuya lengua ancle primero el lugar, o que enuncie la relación al final,
corrompería el paquete al hablarlo en su orden natural.

La v0.5 rompe esa dependencia: **cada campo viaja con su etiqueta**. El
orden deja de ser estructura y pasa a ser estilo — se conserva como
metadato (`meta.grammar.order`) en vez de perderse, y un `SyntaxProfile`
aprende el orden del interlocutor para poder responderle en su sintaxis.

    orden ≠ significado. El orden es la firma del hablante.

Formato binario etiquetado (versión 0x02 de la trama):

    "WSP" | 0x02 | nº paquetes
    por paquete:  nº campos | campo…
    campo:        etiqueta (1 byte) | carga (según etiqueta)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
from enum import IntEnum

from .concepts import Concept, concept_name, resolve
from .emotion import AXES, Emotion
from .primitives import Primitive
from .primitives_science import Element, Quantity, SciPrimitive
from .symbol import _decode_concept, _encode_concept, Message, Symbol

_MAGIC = b"WSP"
TAGGED_VERSION = 0x02

# Ranuras estructurales del paquete, en su orden canónico interno.
_SLOTS = ("source", "relation", "action", "target", "time", "space")


class FieldTag(IntEnum):
    """Etiquetas de campo (4 bits útiles: 0..15).

    Los mismos códigos etiquetan la trama binaria y el acorde polifónico,
    de modo que ambas máscaras comparten gramática.
    """

    CONT = 0          # continuación: añade 5 bits a la carga anterior (acústico)
    SOURCE = 1
    RELATION = 2
    ACTION = 3
    TARGET = 4
    TIME = 5
    SPACE = 6
    EMO_VALENCE = 7
    EMO_AROUSAL = 8
    EMO_DOMINANCE = 9
    EMO_CERTAINTY = 10
    EMO_URGENCY = 11
    EMO_BOND = 12
    QUANTITY = 13
    ELEMENT = 14
    SCI = 15          # átomo del plano científico

    @property
    def slot(self) -> str | None:
        """Nombre de la ranura de `Symbol`, si la etiqueta es estructural."""
        return _SLOTS[self - 1] if 1 <= self <= 6 else None

    @property
    def axis(self) -> str | None:
        """Nombre del eje emocional, si la etiqueta es emocional."""
        return AXES[self - 7] if 7 <= self <= 12 else None


_SLOT_TAGS = {slot: FieldTag(i + 1) for i, slot in enumerate(_SLOTS)}
_AXIS_TAGS = {axis: FieldTag(i + 7) for i, axis in enumerate(AXES)}


@dataclass
class Field:
    """Un campo etiquetado: la unidad de la gramática agnóstica."""

    tag: FieldTag
    value: object  # Concept | float | Quantity | Element | SciPrimitive

    def describe(self) -> str:
        if isinstance(self.value, (Quantity, Element)):
            text = self.value.notation() if isinstance(self.value, Quantity) else self.value.symbol
        elif isinstance(self.value, SciPrimitive):
            text = self.value.name
        elif isinstance(self.value, float):
            text = f"{self.value:+.2f}"
        else:
            text = concept_name(self.value) or "∅"
        return f"{self.tag.name}={text}"


# -- descomposición y recomposición -------------------------------------------------

def fields_of(symbol: Symbol, include_neutral_emotion: bool = False) -> list[Field]:
    """Descompone un paquete en campos etiquetados (orden canónico)."""
    fields: list[Field] = []
    for slot in _SLOTS:
        concept = getattr(symbol, slot)
        if concept is not None:
            fields.append(Field(_SLOT_TAGS[slot], concept))

    science = symbol.meta.get("science") or {}
    for name in science.get("atoms", []):
        atom = SciPrimitive.lookup(name)
        if atom is not None:
            fields.append(Field(FieldTag.SCI, atom))
    if "element" in science:
        fields.append(Field(FieldTag.ELEMENT, Element(int(science["element"]))))
    if "quantity" in science:
        spec = science["quantity"]
        fields.append(Field(FieldTag.QUANTITY, _quantity_from_spec(spec)))

    for axis in AXES:
        value = getattr(symbol.emotion, axis)
        if include_neutral_emotion or abs(value) >= 0.005:
            fields.append(Field(_AXIS_TAGS[axis], value))
    return fields


def normalize(fields: list[Field], order: list[FieldTag] | None = None) -> Symbol:
    """Recompone un paquete a partir de campos en **cualquier orden**.

    El orden observado se conserva en `meta.grammar.order`: la sintaxis
    del hablante es información, no ruido.
    """
    slots: dict[str, Concept] = {}
    emotion_values: dict[str, float] = {}
    science: dict = {}

    for item in fields:
        tag = item.tag
        if tag.slot:
            slots[tag.slot] = item.value
        elif tag.axis:
            emotion_values[tag.axis] = float(item.value)
        elif tag is FieldTag.SCI:
            science.setdefault("atoms", []).append(item.value.name)
        elif tag is FieldTag.ELEMENT:
            science["element"] = item.value.Z
        elif tag is FieldTag.QUANTITY:
            science["quantity"] = _quantity_to_spec(item.value)

    meta: dict = {"grammar": {"order": [t.name for t in (order or [f.tag for f in fields])]}}
    if science:
        meta["science"] = science
    return Symbol(emotion=Emotion(**emotion_values), meta=meta, **slots)


def _quantity_to_spec(quantity: Quantity) -> dict:
    return {
        "mantissa": quantity.mantissa,
        "exponent": quantity.exponent,
        "dimension": list(quantity.dimension.as_tuple()),
    }


def _quantity_from_spec(spec: dict) -> Quantity:
    from .primitives_science import Dimension

    return Quantity(
        int(spec["mantissa"]),
        int(spec.get("exponent", 0)),
        Dimension(*spec.get("dimension", [0] * 7)),
    )


# -- trama binaria etiquetada -----------------------------------------------------

def encode_field(item: Field) -> bytes:
    tag = item.tag
    if tag.slot:
        return bytes([tag]) + _encode_concept(item.value)
    if tag.axis:
        return bytes([tag, int(round(float(item.value) * 100)) & 0xFF])
    if tag is FieldTag.SCI:
        return bytes([tag, item.value.code])
    if tag is FieldTag.ELEMENT:
        return bytes([tag]) + item.value.to_bytes()
    if tag is FieldTag.QUANTITY:
        return bytes([tag]) + item.value.to_bytes()
    raise ValueError(f"etiqueta no serializable: {tag!r}")


def decode_field(data: bytes, offset: int) -> tuple[Field, int]:
    tag = FieldTag(data[offset])
    offset += 1
    if tag.slot:
        concept, offset = _decode_concept(data, offset)
        return Field(tag, concept), offset
    if tag.axis:
        raw = data[offset]
        value = (raw - 256 if raw > 127 else raw) / 100.0
        return Field(tag, value), offset + 1
    if tag is FieldTag.SCI:
        return Field(tag, SciPrimitive.by_code(data[offset])), offset + 1
    if tag is FieldTag.ELEMENT:
        element, offset = Element.from_bytes(data, offset)
        return Field(tag, element), offset
    if tag is FieldTag.QUANTITY:
        quantity, offset = Quantity.from_bytes(data, offset)
        return Field(tag, quantity), offset
    raise ValueError(f"etiqueta no deserializable: {tag!r}")


def encode_tagged(message: Message, order: list[FieldTag] | None = None) -> bytes:
    """Serializa un mensaje en la trama etiquetada (versión 0x02).

    `order` fija la sintaxis de emisión: los campos se emiten en ese
    orden y el receptor los recompone igual, porque no depende de él.
    """
    if len(message.packets) > 255:
        raise ValueError("máximo 255 paquetes por mensaje")
    out = bytearray(_MAGIC + bytes([TAGGED_VERSION, len(message.packets)]))
    for packet in message.packets:
        fields = fields_of(packet)
        if order:
            fields = sort_fields(fields, order)
        if len(fields) > 255:
            raise ValueError("máximo 255 campos por paquete")
        out.append(len(fields))
        for item in fields:
            out += encode_field(item)
    return bytes(out)


def decode_tagged(data: bytes) -> Message:
    """Lee la trama etiquetada. El orden de los campos es irrelevante."""
    if data[:3] != _MAGIC:
        raise ValueError("cabecera binaria inválida: se esperaba b'WSP'")
    if data[3] != TAGGED_VERSION:
        raise ValueError(
            f"esta trama no es etiquetada (versión {data[3]:#04x}); usa Message.from_bytes"
        )
    count = data[4]
    offset = 5
    packets = []
    for _ in range(count):
        n_fields = data[offset]
        offset += 1
        fields = []
        for _ in range(n_fields):
            item, offset = decode_field(data, offset)
            fields.append(item)
        packets.append(normalize(fields))
    return Message(packets=packets)


def sort_fields(fields: list[Field], order: list[FieldTag]) -> list[Field]:
    """Reordena los campos según una sintaxis dada (los no listados van al final)."""
    rank = {tag: i for i, tag in enumerate(order)}
    return sorted(fields, key=lambda f: (rank.get(f.tag, len(order)), int(f.tag)))


# -- perfil sintáctico del interlocutor ----------------------------------------------

@dataclass
class SyntaxProfile:
    """Aprende en qué orden coloca los campos un emisor concreto.

    No se usa para decodificar —la trama etiquetada no lo necesita— sino
    para **responder en la sintaxis del otro**: la cortesía de hablar en
    el orden en que el interlocutor piensa.
    """

    name: str = "desconocido"
    _position_sum: dict[FieldTag, float] = dataclass_field(default_factory=lambda: defaultdict(float))
    _counts: dict[FieldTag, int] = dataclass_field(default_factory=lambda: defaultdict(int))
    samples: int = 0

    def observe(self, order: list[FieldTag]) -> None:
        """Registra el orden de campos de un paquete recibido."""
        if not order:
            return
        last = len(order) - 1
        for position, tag in enumerate(order):
            self._position_sum[tag] += position / last if last else 0.0
            self._counts[tag] += 1
        self.samples += 1

    def observe_message(self, message: Message) -> None:
        for packet in message.packets:
            names = (packet.meta.get("grammar") or {}).get("order") or []
            self.observe([FieldTag[name] for name in names if name in FieldTag.__members__])

    def mean_position(self, tag: FieldTag) -> float | None:
        count = self._counts.get(tag, 0)
        return None if not count else self._position_sum[tag] / count

    def emission_order(self) -> list[FieldTag]:
        """La sintaxis aprendida: etiquetas ordenadas por posición media."""
        known = [tag for tag in FieldTag if self._counts.get(tag)]
        return sorted(known, key=lambda t: (self.mean_position(t), int(t)))

    def render(self, message: Message) -> bytes:
        """Serializa un mensaje en el orden nativo del interlocutor."""
        return encode_tagged(message, order=self.emission_order())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "samples": self.samples,
            "order": [tag.name for tag in self.emission_order()],
            "mean_position": {
                tag.name: round(self.mean_position(tag), 4)
                for tag in FieldTag
                if self._counts.get(tag)
            },
        }
