"""ECHO-WSP — Wired Symbolic Protocol.

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
from .multiband import analyze, emit_handshake, translate_alien_handshake
from .primitives_science import Dimension, Element, Quantity, SciPrimitive
from .grammar import Field, FieldTag, SyntaxProfile, decode_tagged, encode_tagged, normalize
from .multiphonic import Chord, listen_chords, symbol_to_chords
from .discovery import PhoneticMap, Signature, decode_with_map, observe

__version__ = "0.5.0"

__all__ = [
    "analyze",
    "AXES",
    "Category",
    "Chord",
    "Concept",
    "decode_tagged",
    "decode_with_map",
    "define",
    "Derived",
    "Dimension",
    "Element",
    "emit_handshake",
    "Emotion",
    "encode",
    "encode_tagged",
    "Field",
    "FieldTag",
    "inspect_svg",
    "is_builtin",
    "listen",
    "listen_chords",
    "Message",
    "normalize",
    "normalize_token",
    "observe",
    "parse_compact",
    "parse_compact_message",
    "PhoneticMap",
    "Primitive",
    "PROTOCOL",
    "Quantity",
    "registry",
    "render_message",
    "render_svg",
    "render_svg_file",
    "render_symbol",
    "render_wav",
    "resolve",
    "SciPrimitive",
    "Signature",
    "Symbol",
    "symbol_to_chords",
    "SyntaxProfile",
    "synthesize",
    "translate_alien_handshake",
    "VERSION",
    "__version__",
]
