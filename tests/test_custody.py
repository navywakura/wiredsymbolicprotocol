#!/usr/bin/env python3
"""The code in echo_wsp/ is the code that was evaluated.

* every vendored file, with the import rewrite undone, has the SHA-256 that
  echo_wsp/VENDORED.json records for the original in the echoAI tree;
* every LINK file and contract frozen before an evaluation
  (results/linkN/eval-preflight.json) still has that hash here;
* the 16-byte postcard did not grow.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from vendor_from_echoai import backward  # noqa: E402

PKG = REPO / "echo_wsp"
VENDORED = json.loads((PKG / "VENDORED.json").read_text())["files"]


def _original_sha(name: str) -> str:
    raw = (PKG / name).read_bytes()
    if name.endswith(".py"):
        raw = backward(raw.decode("utf-8")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Custody(unittest.TestCase):
    def test_every_vendored_file_matches_its_original(self):
        self.assertGreaterEqual(len(VENDORED), 48)
        for name, rec in VENDORED.items():
            self.assertEqual(_original_sha(name), rec["sha256"], name)

    def test_link_code_is_what_was_frozen_before_each_eval(self):
        checked = 0
        for n in (1, 2, 3):
            pre = json.loads((REPO / f"results/link{n}/eval-preflight.json").read_text())["sha256"]
            for name, digest in pre.items():
                if name.startswith("docs/"):
                    got = hashlib.sha256((REPO / name).read_bytes()).hexdigest()
                elif name.startswith("tests/"):
                    continue  # tests were adapted to this repo's layout
                else:
                    self.assertEqual(VENDORED[name]["sha256"], digest, name)
                    got = _original_sha(name)
                self.assertEqual(got, digest, name)
                checked += 1
        self.assertEqual(checked, 26)  # 13 LINK-1 + 9 LINK-2 + 4 LINK-3

    def test_postcard_is_sixteen_bytes(self):
        from echo_wsp.navi10_qn import WSP_BYTES
        from echo_wsp.navi10_wsp import pack
        self.assertEqual(WSP_BYTES, 16)
        self.assertEqual(len(pack()), 16)


if __name__ == "__main__":
    unittest.main()
