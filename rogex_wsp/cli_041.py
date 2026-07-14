"""Compatibilidad CLI para ROGEX-WSP v0.4.1.

Conserva todos los comandos existentes y sustituye únicamente las rutas
``audio``/``listen`` por el transporte acústico reversible del paquete.
"""

from __future__ import annotations

from . import cli as legacy
from .roundtrip_audio import listen_lossless, render_wav_lossless
from .symbol_to_text import render_message


def _cmd_audio(args) -> int:
    message = legacy._load_message(args)
    path = render_wav_lossless(message, args.output)
    print(f"wav escrito: {path}")
    return 0


def _cmd_listen(args) -> int:
    message = listen_lossless(args.wav)
    if args.compact:
        print(message.compact())
        print(f"es: {render_message(message, 'es')}")
    else:
        print(message.to_json())
    return 0


def main(argv: list[str] | None = None) -> int:
    # `legacy.main` construye el parser después de estas sustituciones, por lo
    # que conserva exactamente la CLI anterior con los dos handlers nuevos.
    legacy.__version__ = "0.4.1"
    legacy._cmd_audio = _cmd_audio
    legacy._cmd_listen = _cmd_listen
    return legacy.main(argv)
