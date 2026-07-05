"""Capa S de ROGEX-WSP: el paquete simbólico.

    S = I + E

La unidad de comunicación no es una palabra: es un paquete con la
estructura gramatical del protocolo (Fase 3):

    [ORIGEN] [RELACIÓN(ACCIÓN)] [DESTINO] [TIEMPO] [ESPACIO] + EMOCIÓN

Un `Message` agrupa uno o más paquetes y se serializa a JSON (formato
intermedio para máquinas) o a binario compacto (render M de bajo nivel).
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

from .concepts import (
    Concept,
    Derived,
    concept_name,
    concept_atoms,
    define,
    is_builtin,
    resolve,
)
from .emotion import AXES, Emotion
from .primitives import Category, Primitive

PROTOCOL = "rogex-wsp"
VERSION = "0.1"

_SLOTS = ("source", "relation", "action", "target", "time", "space")

_MAGIC = b"WSP"
_VERSION_BYTE = 0x01


@dataclass
class Symbol:
    """Un paquete de significado: información + emoción."""

    source: Concept | None = None
    relation: Concept | None = None
    action: Concept | None = None
    target: Concept | None = None
    time: Concept | None = None
    space: Concept | None = None
    emotion: Emotion = field(default_factory=Emotion)
    meta: dict = field(default_factory=dict)

    # -- introspección -----------------------------------------------------
    def slots(self) -> dict[str, Concept]:
        return {name: getattr(self, name) for name in _SLOTS if getattr(self, name) is not None}

    def atoms(self) -> tuple[Primitive, ...]:
        """Todos los átomos (Capa 1) involucrados en el paquete."""
        atoms: list[Primitive] = []
        for concept in self.slots().values():
            for atom in concept_atoms(concept):
                if atom not in atoms:
                    atoms.append(atom)
        return tuple(atoms)

    def compact(self) -> str:
        """Forma compacta legible por máquina:

        YO → DESEAR(COMUNICAR) → OTRO @AHORA @WIRED | E[V+0.70 ... B+0.80]
        """
        relation = concept_name(self.relation) or "∅"
        if self.action is not None:
            relation += f"({concept_name(self.action)})"
        parts = [concept_name(self.source) or "∅", "→", relation]
        if self.target is not None:
            parts += ["→", concept_name(self.target)]
        if self.time is not None:
            parts.append(f"@{concept_name(self.time)}")
        if self.space is not None:
            parts.append(f"@{concept_name(self.space)}")
        parts.append(f"| E[{self.emotion.signature()}]")
        return " ".join(parts)

    # -- JSON ---------------------------------------------------------------
    def to_dict(self) -> dict:
        packet: dict = {
            "symbol": {name: concept_name(c) for name, c in self.slots().items()},
            "emotion": self.emotion.to_dict(),
        }
        if self.meta:
            packet["meta"] = dict(self.meta)
        return packet

    @classmethod
    def from_dict(cls, data: dict) -> "Symbol":
        symbol_data = data.get("symbol", {})
        kwargs: dict = {}
        for name in _SLOTS:
            value = symbol_data.get(name)
            if value is not None:
                kwargs[name] = resolve(value)
        return cls(
            emotion=Emotion.from_dict(data.get("emotion", {})),
            meta=dict(data.get("meta", {})),
            **kwargs,
        )

    # -- binario --------------------------------------------------------------
    def to_bytes(self) -> bytes:
        flags = 0
        body = b""
        for bit, name in enumerate(_SLOTS):
            concept = getattr(self, name)
            if concept is not None:
                flags |= 1 << bit
                body += _encode_concept(concept)
        emotion = struct.pack(
            "6b", *(int(round(getattr(self.emotion, axis) * 100)) for axis in AXES)
        )
        return bytes([flags]) + body + emotion

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["Symbol", int]:
        flags = data[offset]
        offset += 1
        kwargs: dict = {}
        for bit, name in enumerate(_SLOTS):
            if flags & (1 << bit):
                concept, offset = _decode_concept(data, offset)
                kwargs[name] = concept
        values = struct.unpack_from("6b", data, offset)
        offset += 6
        emotion = Emotion(**{axis: v / 100 for axis, v in zip(AXES, values)})
        return cls(emotion=emotion, **kwargs), offset


def _encode_concept(concept: Concept) -> bytes:
    """Primitivo: 1 byte (0..31). Derivado: 0x80|n átomos, átomos, nombre utf-8."""
    if isinstance(concept, Primitive):
        return bytes([concept.code])
    name = concept.name.encode("utf-8")
    if len(concept.components) > 31 or len(name) > 255:
        raise ValueError(f"concepto derivado demasiado grande: {concept.name}")
    return (
        bytes([0x80 | len(concept.components)])
        + bytes(p.code for p in concept.components)
        + bytes([len(name)])
        + name
    )


def _decode_concept(data: bytes, offset: int) -> tuple[Concept, int]:
    head = data[offset]
    offset += 1
    if not head & 0x80:
        return Primitive.by_code(head), offset
    n_components = head & 0x1F
    components = [Primitive.by_code(data[offset + i]) for i in range(n_components)]
    offset += n_components
    name_len = data[offset]
    offset += 1
    name = data[offset : offset + name_len].decode("utf-8")
    offset += name_len
    try:
        concept = resolve(name)
    except KeyError:
        # Generatividad por el cable: el receptor aprende el concepto nuevo.
        concept = define(name, components)
    return concept, offset


@dataclass
class Message:
    """Uno o más paquetes simbólicos, con las definiciones que transportan."""

    packets: list[Symbol] = field(default_factory=list)

    # -- JSON ---------------------------------------------------------------
    def to_dict(self, include_defines: str = "custom") -> dict:
        """`include_defines`: "custom" (solo conceptos no de fábrica), "all" o "none"."""
        data: dict = {"protocol": PROTOCOL, "version": VERSION}
        defines: dict[str, dict] = {}
        if include_defines != "none":
            for packet in self.packets:
                for concept in packet.slots().values():
                    if isinstance(concept, Derived):
                        if include_defines == "all" or not is_builtin(concept.name):
                            defines[concept.name] = concept.to_spec()
        if defines:
            data["defines"] = defines
        data["packets"] = [packet.to_dict() for packet in self.packets]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        for name, spec in (data.get("defines") or {}).items():
            try:
                resolve(name)
            except KeyError:
                define(
                    name,
                    [resolve(c) for c in spec.get("components", [])],
                    es=spec.get("es", ""),
                    en=spec.get("en", ""),
                    emotion=Emotion.from_dict(spec["emotion"]) if spec.get("emotion") else None,
                    category=Category(spec.get("category", Category.ENTITY.value)),
                    article_es=spec.get("article_es", ""),
                )
        if "packets" in data:
            packets = [Symbol.from_dict(p) for p in data["packets"]]
        elif "symbol" in data:  # forma de paquete único, como en el documento de diseño
            packets = [Symbol.from_dict(data)]
        else:
            raise ValueError("el mensaje no contiene 'packets' ni 'symbol'")
        return cls(packets=packets)

    def to_json(self, indent: int | None = 2, include_defines: str = "custom") -> str:
        return json.dumps(
            self.to_dict(include_defines=include_defines),
            ensure_ascii=False,
            indent=indent,
        )

    @classmethod
    def from_json(cls, text: str) -> "Message":
        return cls.from_dict(json.loads(text))

    # -- binario --------------------------------------------------------------
    def to_bytes(self) -> bytes:
        if len(self.packets) > 255:
            raise ValueError("máximo 255 paquetes por mensaje binario")
        out = _MAGIC + bytes([_VERSION_BYTE, len(self.packets)])
        for packet in self.packets:
            out += packet.to_bytes()
        return out

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        if data[:3] != _MAGIC:
            raise ValueError("cabecera binaria inválida: se esperaba b'WSP'")
        if data[3] != _VERSION_BYTE:
            raise ValueError(f"versión binaria no soportada: {data[3]}")
        count = data[4]
        offset = 5
        packets = []
        for _ in range(count):
            packet, offset = Symbol.from_bytes(data, offset)
            packets.append(packet)
        return cls(packets=packets)

    def compact(self) -> str:
        return "\n".join(packet.compact() for packet in self.packets)
