"""Capa G de ROGEX-WSP: generatividad.

Un concepto derivado no es una palabra nueva: es una composición de
átomos más una firma emocional (Capa 7 del protocolo). Ejemplo:

    soledad  = [ser] + [no-ser] + [desear]  + emoción negativa/distante
    amor     = [ser] + [otro]  + [unir]     + emoción positiva/cercana/continua

El registro es abierto: `define()` crea conceptos nuevos en tiempo de
ejecución, y los mensajes pueden transportar sus definiciones para que
el receptor los aprenda ("generatividad por el cable").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from .emotion import Emotion
from .primitives import Category, Primitive, normalize_token


@dataclass(frozen=True)
class Derived:
    """Concepto compuesto: nombre + átomos componentes + firma emocional por defecto."""

    name: str
    components: tuple[Primitive, ...]
    es: str = ""
    en: str = ""
    emotion: Emotion | None = None
    category: Category = Category.ENTITY
    article_es: str = ""  # "el" / "la" para el render en español

    def to_spec(self) -> dict:
        spec: dict = {
            "components": [p.name for p in self.components],
            "es": self.es,
            "en": self.en,
            "category": self.category.value,
        }
        if self.emotion is not None:
            spec["emotion"] = self.emotion.to_dict()
        if self.article_es:
            spec["article_es"] = self.article_es
        return spec


Concept = Union[Primitive, Derived]

_REGISTRY: dict[str, Derived] = {}


def define(
    name: str,
    components: list[Primitive] | tuple[Primitive, ...],
    es: str = "",
    en: str = "",
    emotion: Emotion | None = None,
    category: Category = Category.ENTITY,
    article_es: str = "",
) -> Derived:
    """Crea (o reemplaza) un concepto derivado en el registro."""
    canonical = name.strip().upper().replace("-", "_").replace(" ", "_")
    if Primitive.lookup(canonical) is not None:
        raise ValueError(f"'{name}' colisiona con un primitivo del núcleo")
    if not components:
        raise ValueError("un concepto derivado necesita al menos un átomo componente")
    concept = Derived(
        name=canonical,
        components=tuple(components),
        es=es or canonical.lower(),
        en=en or canonical.lower(),
        emotion=emotion,
        category=category,
        article_es=article_es,
    )
    _REGISTRY[normalize_token(canonical)] = concept
    return concept


def resolve(name: str) -> Concept:
    """Resuelve un nombre a primitivo o concepto derivado registrado."""
    primitive = Primitive.lookup(name)
    if primitive is not None:
        return primitive
    derived = _REGISTRY.get(normalize_token(name))
    if derived is not None:
        return derived
    raise KeyError(f"concepto desconocido: {name!r}")


def registry() -> dict[str, Derived]:
    """Copia del registro actual de conceptos derivados (por nombre canónico)."""
    return {d.name: d for d in _REGISTRY.values()}


def is_builtin(name: str) -> bool:
    return normalize_token(name) in _BUILTIN_KEYS


# -- helpers sobre conceptos -------------------------------------------------

def concept_name(concept: Concept | None) -> str | None:
    if concept is None:
        return None
    return concept.name


def concept_atoms(concept: Concept) -> tuple[Primitive, ...]:
    """Descompone cualquier concepto en sus átomos (Capa 1)."""
    if isinstance(concept, Primitive):
        return (concept,)
    return concept.components


def concept_es(concept: Concept) -> str:
    return concept.es


def concept_en(concept: Concept) -> str:
    return concept.en


# -- conceptos derivados de fábrica ------------------------------------------
# Composiciones tomadas del documento de diseño del protocolo.

P = Primitive

define(
    "AMOR", [P.SER, P.OTRO, P.UNIR], es="amor", en="love",
    emotion=Emotion(valence=0.9, arousal=0.6, certainty=0.8, bond=0.95),
    article_es="el",
)
define(
    "SOLEDAD", [P.SER, P.NO_SER, P.DESEAR], es="soledad", en="loneliness",
    emotion=Emotion(valence=-0.7, arousal=0.3, certainty=0.6, bond=-0.8),
    article_es="la",
)
define(
    "COMUNICAR", [P.UNIR, P.PREGUNTAR, P.RESPONDER], es="comunicar", en="communicate",
    category=Category.RELATION,
)
define(
    "CONEXION", [P.UNIR, P.OTRO], es="conexión", en="connection",
    emotion=Emotion(valence=0.5, bond=0.7),
    article_es="la",
)
define(
    "PELIGRO", [P.TEMER, P.DESTRUIR, P.POSIBLE], es="peligro", en="danger",
    emotion=Emotion(valence=-0.9, arousal=0.9, certainty=0.8, urgency=0.9),
    article_es="el",
)
define(
    "BIENVENIDA", [P.OTRO, P.AQUI, P.ABRIR], es="bienvenida", en="welcome",
    emotion=Emotion(valence=0.7, certainty=0.7, bond=0.8),
    article_es="la",
)
define(
    "CONCIENCIA", [P.SER, P.OBSERVAR, P.DESCONOCIDO], es="conciencia", en="consciousness",
    article_es="la",
)
define(
    "WIRED", [P.DENTRO, P.UNIR, P.ALLI], es="la Wired", en="the Wired",
    category=Category.SPACE,
    article_es="la",
)
define(
    "BUSCAR", [P.DESEAR, P.OBSERVAR, P.DESCONOCIDO], es="buscar", en="seek",
    category=Category.RELATION,
)

_BUILTIN_KEYS = frozenset(_REGISTRY.keys())
