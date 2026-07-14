"""ROGEX-WSP — Wired Symbolic Protocol.

Protocolo de significado: la unidad de comunicación no es la palabra,
sino un paquete de información + emoción que puede renderizarse como
texto, sonido, glifo, JSON o binario.

    L = G[S(M, I, E)]
"""

from .primitives import Category, Primitive, normalize_token
from .emotion import AXES, Emotion
from .concepts import Concept, Derived, define, is_builtin, registry, resolve
from .symbol import PROTOCOL, VERSION, Message, Symbol
from .text_to_symbol import encode
from .symbol_to_text import render_message, render_symbol
from .audio import render_wav, synthesize
from .glyph import render_svg, render_svg_file
from .compact import parse_compact, parse_compact_message
from .listen import listen
from .glyph_reader import inspect_svg

__version__ = "0.2.0"

__all__ = [
    "AXES",
    "Category",
    "Concept",
    "Derived",
    "Emotion",
    "Message",
    "PROTOCOL",
    "Primitive",
    "Symbol",
    "VERSION",
    "__version__",
    "define",
    "encode",
    "inspect_svg",
    "is_builtin",
    "listen",
    "normalize_token",
    "parse_compact",
    "parse_compact_message",
    "registry",
    "render_message",
    "render_svg",
    "render_svg_file",
    "render_symbol",
    "render_wav",
    "resolve",
    "synthesize",
]
