"""A veteran ECHO agent in its own process. It speaks only bytes.

    python3 -m echo_wsp.link1.peer speak --seed S   # live 256 turns, print claims
    python3 -m echo_wsp.link1.peer serve --seed S   # live, then answer ASK frames

Frames are the fixed 22-byte envelope, written back to back on stdout. In
`serve` mode each ASK read from stdin is answered by one count byte and
that many frames; a BYE frame (or end of input) ends the process. Nothing
but frames crosses the pipe: no Python objects, no shared memory.
"""

from __future__ import annotations

import argparse
import sys

from echo_wsp.link1 import frame as fr
from echo_wsp.link1.agent import TalkingAgent
from echo_wsp.link1.world import LayoutRing


def veteran(seed: int, agent_id: int = 1) -> TalkingAgent:
    a = TalkingAgent(agent_id, env=LayoutRing(seed))
    a.run(256)
    return a


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("speak", "serve"))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--id", type=int, default=1)
    args = ap.parse_args(argv)
    a = veteran(args.seed, args.id)
    out = sys.stdout.buffer
    if args.mode == "speak":
        for f in a.broadcast():
            out.write(f.to_bytes())
        out.flush()
        return 0
    inp = sys.stdin.buffer
    while True:
        raw = inp.read(fr.FRAME_BYTES)
        if len(raw) < fr.FRAME_BYTES:
            return 0
        f = fr.parse(raw)
        if f is None:
            out.write(bytes([0]))
            out.flush()
            continue
        if f.act == fr.ACT_BYE:
            return 0
        replies = a.hear(f) or []
        out.write(bytes([len(replies)]))
        for r in replies:
            out.write(r.to_bytes())
        out.flush()


if __name__ == "__main__":
    raise SystemExit(main())
