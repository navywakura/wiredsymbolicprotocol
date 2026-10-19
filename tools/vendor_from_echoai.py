#!/usr/bin/env python3
"""Copy the LINK code, and the part of echoAI it runs on, into echo_wsp/.

    python3 tools/vendor_from_echoai.py /path/to/RXos

LINK-1/2/3 were written and evaluated inside the echoAI tree
(`echoai/link1..3`, on top of `echoai/nexus0` and the `navi10_*` modules).
Here they live in one package. The only change is the import path:

    echoai.link   -> echo_wsp.link      echoai/link -> echo_wsp/link
    echoai.nexus0 -> echo_wsp.nexus0    from navi10_ -> from echo_wsp.navi10_
    RogexWSP      -> ECHO-WSP v0.5      (the protocol's old name, in one docstring)

`echo_wsp/VENDORED.json` records the SHA-256 of every original file;
tests/test_custody.py undoes the rewrite and checks each copy against it,
and the LINK files also against the hashes frozen before each evaluation.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "echo_wsp"

NEXUS0 = ("__init__", "attend", "constants", "cortex", "cortex_turn", "encoder", "env",
          "escalate", "gate", "lex", "loop", "oracle", "pattern", "plan", "qtable",
          "thought", "types", "world")
NAVI10 = ("navi10_qn", "navi10_cam", "navi10_dag", "navi10_spoke", "navi10_wsp")
LINK = {
    "link1": ("__init__", "agent", "audio_io", "bench", "demo", "frame", "modem", "peer",
              "room", "rs", "speech", "world"),
    "link2": ("__init__", "agent2", "air", "bench", "envelope", "ggwave_runner", "phy",
              "speech2"),
    "link3": ("__init__", "agent3", "bench", "media"),
}

_FWD = [("echoai.link", "echo_wsp.link"), ("echoai/link", "echo_wsp/link"),
        ("echoai.nexus0", "echo_wsp.nexus0"), ("RogexWSP", "ECHO-WSP v0.5")]
_NAVI = re.compile(r"^(\s*)from navi10_", re.M)
_NAVI_BACK = re.compile(r"^(\s*)from echo_wsp\.navi10_", re.M)


def forward(text: str) -> str:
    if "echo_wsp" in text or "ECHO-WSP" in text:
        raise ValueError("source already mentions echo_wsp; the rewrite would not be reversible")
    for a, b in _FWD:
        text = text.replace(a, b)
    return _NAVI.sub(r"\1from echo_wsp.navi10_", text)


def backward(text: str) -> str:
    text = _NAVI_BACK.sub(r"\1from navi10_", text)
    for a, b in _FWD:
        text = text.replace(b, a)
    return text


def _copy(src: Path, dst: Path, record: dict, key: str) -> None:
    raw = src.read_bytes()
    record[key] = {"source": key, "sha256": hashlib.sha256(raw).hexdigest()}
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".py":
        dst.write_text(forward(raw.decode("utf-8")), encoding="utf-8")
    else:
        shutil.copyfile(src, dst)


def main(argv=None) -> int:
    rx = Path((argv or sys.argv[1:])[0]).resolve()
    record: dict = {}
    for m in NAVI10:
        _copy(rx / f"{m}.py", PKG / f"{m}.py", record, f"{m}.py")
    for m in NEXUS0:
        _copy(rx / "echoai/nexus0" / f"{m}.py", PKG / "nexus0" / f"{m}.py", record,
              f"echoai/nexus0/{m}.py")
    _copy(rx / "echoai/nexus0/bank/canonical.json", PKG / "nexus0/bank/canonical.json", record,
          "echoai/nexus0/bank/canonical.json")
    for pkg, mods in LINK.items():
        for m in mods:
            _copy(rx / "echoai" / pkg / f"{m}.py", PKG / pkg / f"{m}.py", record,
                  f"echoai/{pkg}/{m}.py")
    out = {"from": "echoAI tree (navywakura/echoai), import paths rewritten by "
                   "tools/vendor_from_echoai.py; nothing else changed",
           "files": {str(Path(k).relative_to("echoai")) if k.startswith("echoai/") else k: v
                     for k, v in record.items()}}
    (PKG / "VENDORED.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"{len(record)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
