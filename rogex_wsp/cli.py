"""Interfaz de línea de comandos de ROGEX-WSP.

    wsp atoms                                   # los 32 átomos del núcleo
    wsp encode "te quiero"                      # texto → símbolo (JSON)
    wsp encode "te quiero" --compact            # texto → forma máquina
    wsp decode mensaje.json [--lang en]         # símbolo → texto humano
    wsp audio --text "estoy aquí" -o out.wav    # símbolo → sonido
    wsp glyph --text "te quiero" -o out.svg     # símbolo → glifo
    wsp binary --text "peligro"                 # símbolo → binario (hex)
    wsp listen mensaje.wav                      # sonido → símbolo (v0.2)
    wsp inspect mensaje.svg                     # glifo → símbolo (v0.2)
    wsp contact señal.wav                       # saludo de 5 tonos → símbolo (v0.4)
    wsp contact --emit saludo.wav               # emite el saludo de contacto
    wsp demo -o demo_out                        # ejemplos canónicos completos
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

from . import __version__
from .audio import render_wav
from .glyph import render_svg_file
from .primitives import Primitive
from .symbol import Message
from .symbol_to_text import render_message
from .text_to_symbol import encode


def _load_message(args: argparse.Namespace) -> Message:
    """Obtiene un mensaje desde --text, --json (ruta o '-' para stdin)."""
    if getattr(args, "text", None):
        return encode(args.text)
    path = getattr(args, "json", None)
    if path:
        raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        return Message.from_json(raw)
    raise SystemExit("error: se necesita --text o --json")


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def _cmd_atoms(args: argparse.Namespace) -> int:
    print("código  átomo         es           en           categoría")
    print("------  ------------  -----------  -----------  ---------")
    for p in Primitive:
        print(f"{p.code:>6}  {p.name:<12}  {p.es:<11}  {p.en:<11}  {p.category.value}")
    return 0


def _cmd_encode(args: argparse.Namespace) -> int:
    message = encode(args.text)
    if args.compact:
        print(message.compact())
    else:
        print(message.to_json())
    return 0


def _cmd_decode(args: argparse.Namespace) -> int:
    raw = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
    message = Message.from_json(raw)
    print(render_message(message, lang=args.lang, emotion_gloss=args.emotion))
    return 0


def _cmd_audio(args: argparse.Namespace) -> int:
    message = _load_message(args)
    path = render_wav(message, args.output)
    print(f"wav escrito: {path}")
    return 0


def _cmd_glyph(args: argparse.Namespace) -> int:
    message = _load_message(args)
    path = render_svg_file(message, args.output)
    print(f"svg escrito: {path}")
    return 0


def _cmd_binary(args: argparse.Namespace) -> int:
    message = _load_message(args)
    data = message.to_bytes()
    if args.output:
        with open(args.output, "wb") as f:
            f.write(data)
        print(f"binario escrito: {args.output} ({len(data)} bytes)")
    else:
        print(data.hex(" "))
    return 0


def _cmd_listen(args: argparse.Namespace) -> int:
    from .listen import listen
    from .symbol_to_text import render_message

    message = listen(args.wav)
    if args.compact:
        print(message.compact())
        print(f"es: {render_message(message, 'es')}")
    else:
        print(message.to_json())
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    from .glyph_reader import inspect_svg
    from .symbol_to_text import render_message

    message = inspect_svg(args.svg)
    if args.compact:
        print(message.compact())
        print(f"es: {render_message(message, 'es')}")
    else:
        print(message.to_json())
    return 0


def _cmd_contact(args: argparse.Namespace) -> int:
    from .multiband import analyze, emit_handshake, translate_alien_handshake
    from .symbol_to_text import render_message

    if args.emit:
        path = emit_handshake(args.emit, base=args.base)
        print(f"saludo emitido: {path} (base {args.base} Hz)")
        return 0
    if not args.wav:
        raise SystemExit("error: se necesita un WAV o --emit")
    message = translate_alien_handshake(args.wav)
    if message is None:
        report = analyze(args.wav)
        print("sin firma de contacto en la señal")
        print(
            f"capas: {len(report.low_tones)} tonos graves · "
            f"{len(report.mid_tones)} tonos medios · {report.high_onsets} transitorios"
        )
        return 1
    if args.compact:
        print(message.compact())
        print(f"es: {render_message(message, 'es')}")
        print(f"en: {render_message(message, 'en')}")
    else:
        print(message.to_json())
    return 0


_DEMO_PHRASES = [
    "te quiero",
    "estoy aquí",
    "quiero hablar contigo en la wired",
    "estoy solo pero quiero conectar",
    "¿estás ahí?",
    "¡peligro!",
    "no tengan miedo de lo que no conocen",
]


def _cmd_demo(args: argparse.Namespace) -> int:
    os.makedirs(args.output, exist_ok=True)
    for text in _DEMO_PHRASES:
        message = encode(text)
        slug = _slug(text)
        json_path = os.path.join(args.output, f"{slug}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(message.to_json() + "\n")
        wav_path = render_wav(message, os.path.join(args.output, f"{slug}.wav"))
        svg_path = render_svg_file(message, os.path.join(args.output, f"{slug}.svg"))

        print(f"■ «{text}»")
        for line in message.compact().splitlines():
            print(f"    {line}")
        print(f"    es: {render_message(message, 'es')}")
        print(f"    en: {render_message(message, 'en')}")
        print(f"    binario: {message.to_bytes().hex(' ')}")
        print(f"    archivos: {json_path} · {wav_path} · {svg_path}")
        print()
    print(f"demo completa en: {args.output}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wsp",
        description="ROGEX-WSP — Wired Symbolic Protocol (v0.1). "
        "El significado no vive en la palabra: la palabra es solo una máscara.",
    )
    parser.add_argument("--version", action="version", version=f"rogex-wsp {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("atoms", help="lista los 32 primitivos semánticos")
    p.set_defaults(func=_cmd_atoms)

    p = sub.add_parser("encode", help="texto humano → mensaje simbólico")
    p.add_argument("text", help="frase a codificar")
    p.add_argument("--compact", action="store_true", help="forma máquina en vez de JSON")
    p.set_defaults(func=_cmd_encode)

    p = sub.add_parser("decode", help="mensaje simbólico (JSON) → texto humano")
    p.add_argument("json", help="ruta al JSON, o '-' para stdin")
    p.add_argument("--lang", choices=["es", "en"], default="es")
    p.add_argument("--emotion", action="store_true", help="añade glosa emocional")
    p.set_defaults(func=_cmd_decode)

    for name, func, ext in (("audio", _cmd_audio, "wav"), ("glyph", _cmd_glyph, "svg")):
        p = sub.add_parser(name, help=f"mensaje simbólico → {ext}")
        p.add_argument("--text", help="frase a codificar primero")
        p.add_argument("--json", help="ruta a JSON simbólico, o '-' para stdin")
        p.add_argument("-o", "--output", default=f"mensaje.{ext}", help="archivo de salida")
        p.set_defaults(func=func)

    p = sub.add_parser("binary", help="mensaje simbólico → binario compacto")
    p.add_argument("--text", help="frase a codificar primero")
    p.add_argument("--json", help="ruta a JSON simbólico, o '-' para stdin")
    p.add_argument("-o", "--output", help="archivo de salida (por defecto: hex a stdout)")
    p.set_defaults(func=_cmd_binary)

    p = sub.add_parser("listen", help="sonido (WAV) → símbolo: detección de ratios")
    p.add_argument("wav", help="ruta al archivo WAV generado por WSP")
    p.add_argument("--compact", action="store_true", help="forma compacta + texto en vez de JSON")
    p.set_defaults(func=_cmd_listen)

    p = sub.add_parser("inspect", help="glifo (SVG) → símbolo: lectura geométrica")
    p.add_argument("svg", help="ruta al archivo SVG generado por WSP")
    p.add_argument("--compact", action="store_true", help="forma compacta + texto en vez de JSON")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser(
        "contact",
        help="detecta o emite el saludo de contacto de 5 tonos (análisis multibanda)",
    )
    p.add_argument("wav", nargs="?", help="WAV a analizar (omitir con --emit)")
    p.add_argument("--emit", metavar="SALIDA.wav", help="emite el saludo en vez de analizar")
    p.add_argument("--base", type=float, default=293.66, help="frecuencia del primer tono al emitir (Hz)")
    p.add_argument("--compact", action="store_true", help="forma compacta + texto en vez de JSON")
    p.set_defaults(func=_cmd_contact)

    p = sub.add_parser("demo", help="ejecuta los ejemplos canónicos y genera archivos")
    p.add_argument("-o", "--output", default="demo_out", help="directorio de salida")
    p.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        # salida cortada (p. ej. `wsp atoms | head`): no es un error
        sys.stderr.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
