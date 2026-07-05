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

__version__ = "0.1.0"

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
    "is_builtin",
    "normalize_token",
    "registry",
    "render_message",
    "render_svg",
    "render_svg_file",
    "render_symbol",
    "render_wav",
    "resolve",
    "synthesize",
]
