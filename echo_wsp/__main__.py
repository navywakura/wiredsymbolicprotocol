"""python3 -m echo_wsp <command> [args]: one entry point for the LINK tools."""

from __future__ import annotations

import importlib
import sys

COMMANDS = {
    "demo": ("echo_wsp.link1.demo", "two agents talk through a simulated echoing room (LINK-1)"),
    "peer": ("echo_wsp.link1.peer", "one agent as a process that speaks or answers (LINK-1)"),
    "bench1": ("echo_wsp.link1.bench", "LINK-1 experiments"),
    "bench2": ("echo_wsp.link2.bench", "LINK-2 experiments"),
    "air": ("echo_wsp.link2.air", "LINK-2 real air and the ggwave comparison"),
    "bench3": ("echo_wsp.link3.bench", "LINK-3 experiments: --split dev|eval"),
    "media": ("echo_wsp.link3.media", "LINK-3 conversations as WAV + transcript: OUT_DIR"),
    "v05": ("echo_wsp.v05.cli_041", "the earlier v0.5 protocol CLI (encode, audio, glyph...)"),
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print("usage: python3 -m echo_wsp <command> [args]\n")
        for k, (_m, h) in COMMANDS.items():
            print(f"  {k:<7} {h}")
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    mod = importlib.import_module(COMMANDS[argv[0]][0])
    sys.argv = [f"echo_wsp {argv[0]}"] + argv[1:]
    return int(mod.main(argv[1:]) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
