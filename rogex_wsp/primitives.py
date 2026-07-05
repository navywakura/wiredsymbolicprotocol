"""Capa atómica de ROGEX-WSP: los 32 primitivos semánticos.

No son palabras: son átomos de significado (Fase 1 del protocolo).
Cada primitivo tiene un código de 5 bits (0..31), un nombre canónico,
una forma en español, una forma en inglés y una categoría.
"""

from __future__ import annotations

import unicodedata
from enum import Enum


def normalize_token(text: str) -> str:
    """Normaliza un token para búsquedas: minúsculas, sin acentos ni separadores."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower().replace("-", "").replace("_", "").replace(" ", "")


class Category(str, Enum):
    ENTITY = "entity"      # quién / qué
    SPACE = "space"        # dónde
    TIME = "time"          # cuándo
    RELATION = "relation"  # qué ocurre (acciones y relaciones)
    MODAL = "modal"        # lógica / posibilidad / conocimiento


class Primitive(Enum):
    """Los 32 átomos universales. El valor del enum es su código binario (5 bits)."""

    # -- entidad --------------------------------------------------------
    SER = (0, "ser", "be", Category.ENTITY)
    NO_SER = (1, "no-ser", "not-be", Category.ENTITY)
    YO = (2, "yo", "self", Category.ENTITY)
    OTRO = (3, "otro", "other", Category.ENTITY)
    # -- espacio --------------------------------------------------------
    AQUI = (4, "aquí", "here", Category.SPACE)
    ALLI = (5, "allí", "there", Category.SPACE)
    DENTRO = (6, "dentro", "inside", Category.SPACE)
    FUERA = (7, "fuera", "outside", Category.SPACE)
    # -- tiempo ---------------------------------------------------------
    AHORA = (8, "ahora", "now", Category.TIME)
    ANTES = (9, "antes", "before", Category.TIME)
    DESPUES = (10, "después", "after", Category.TIME)
    # -- relación / acción ----------------------------------------------
    UNIR = (11, "unir", "join", Category.RELATION)
    SEPARAR = (12, "separar", "separate", Category.RELATION)
    CAMBIAR = (13, "cambiar", "change", Category.RELATION)
    OBSERVAR = (14, "observar", "observe", Category.RELATION)
    PREGUNTAR = (15, "preguntar", "ask", Category.RELATION)
    RESPONDER = (16, "responder", "answer", Category.RELATION)
    DESEAR = (17, "desear", "desire", Category.RELATION)
    TEMER = (18, "temer", "fear", Category.RELATION)
    RECORDAR = (19, "recordar", "remember", Category.RELATION)
    OLVIDAR = (20, "olvidar", "forget", Category.RELATION)
    CREAR = (21, "crear", "create", Category.RELATION)
    DESTRUIR = (22, "destruir", "destroy", Category.RELATION)
    SUBIR = (23, "subir", "rise", Category.RELATION)
    BAJAR = (24, "bajar", "descend", Category.RELATION)
    ABRIR = (25, "abrir", "open", Category.RELATION)
    CERRAR = (26, "cerrar", "close", Category.RELATION)
    # -- modal / lógica ---------------------------------------------------
    CAUSA = (27, "causa", "cause", Category.MODAL)
    EFECTO = (28, "efecto", "effect", Category.MODAL)
    POSIBLE = (29, "posible", "possible", Category.MODAL)
    IMPOSIBLE = (30, "imposible", "impossible", Category.MODAL)
    DESCONOCIDO = (31, "desconocido", "unknown", Category.MODAL)

    def __new__(cls, code: int, es: str, en: str, category: Category):
        obj = object.__new__(cls)
        obj._value_ = code
        obj.code = code
        obj.es = es
        obj.en = en
        obj.category = category
        return obj

    @classmethod
    def by_code(cls, code: int) -> "Primitive":
        return cls(code)

    @classmethod
    def lookup(cls, name: str) -> "Primitive | None":
        """Busca un primitivo por nombre canónico, español o inglés (tolerante a acentos)."""
        return _BY_NAME.get(normalize_token(name))


_BY_NAME: dict[str, Primitive] = {}
for _p in Primitive:
    for _key in (_p.name, _p.es, _p.en):
        _BY_NAME[normalize_token(_key)] = _p

assert len(Primitive) == 32, "el núcleo del protocolo son exactamente 32 átomos"
