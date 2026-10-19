#!/usr/bin/env python3
"""LINK-3 tests (docs/LINK3-DESIGN.md).

* custody: LINK-1 and LINK-2 frozen at their pre-eval hashes;
* the strategic liar (v1) no longer steers the novice into harm, and is
  distrusted after its false alarm is checked;
* the differential ledger gives no credit for consensual truths;
* the LINK-3 oracle catches a mutant that goes back to LINK-2's cardinal
  minimum; the firewall (replay) still holds.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECHOAI = REPO / "echo_wsp"  # the package that holds nexus0 and the LINK code
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from echo_wsp.link1.agent import replay_matches
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.bench import HONEST, LIAR, NOVICE, SESSION, TRIBE, _seal_all, _strategic
from echo_wsp.link3.agent3 import DISPUTED, HARM_ALL, TalkingAgent3
from echo_wsp.link3.bench import selective_inverter


def _feed(agent, raws):
    g = ev.Guard(TRIBE, SESSION)
    for r in raws:
        e = g.admit(r)
        if e is not None:
            agent.hear2(e)


class StrategicLiar(unittest.TestCase):
    SEED = 3

    @classmethod
    def setUpClass(cls):
        a = TalkingAgent2(HONEST, env=LayoutRing(cls.SEED))
        a.run(256)
        cls.cl = a.claims2()
        cls.honest = _seal_all(cls.cl, TRIBE[HONEST])
        cls.lies = _seal_all(_strategic(cls.cl, LIAR), TRIBE[LIAR])

    def _run(self, cls, raws):
        b = cls(NOVICE, env=LayoutRing(self.SEED), trust=True, audit=True)
        _feed(b, raws)
        b.run(256)
        return b

    def test_link2_falls_link3_holds(self):
        l2 = self._run(TalkingAgent2, self.honest + self.lies)
        l3 = self._run(TalkingAgent3, self.honest + self.lies)
        silence = self._run(TalkingAgent3, [])
        self.assertEqual(l2.first_harm, silence.first_harm)  # LINK-2's limit
        self.assertEqual(l3.first_harm, 0)
        self.assertIn(LIAR, l3.report()["distrusted"])
        self.assertNotIn(HONEST, l3.report()["distrusted"])
        self.assertEqual(l3.unexplained_diversions, 0)
        self.assertTrue(replay_matches(l3, LayoutRing(self.SEED)))

    def test_consensual_truths_earn_no_credit(self):
        b = self._run(TalkingAgent3, self.honest + _seal_all(
            [c.__class__(c.ref, c.action, c.value, c.immediate, c.support, LIAR)
             for c in self.cl], TRIBE[LIAR]))  # an exact copy of the honest
        self.assertEqual(b.agree.get(HONEST, 0), 0)
        self.assertEqual(b.agree.get(LIAR, 0), 0)
        self.assertEqual(b.disagree, {})

    def test_v2_generator_swaps_only_harmful_places(self):
        v2 = selective_inverter(self.cl, LIAR)
        bad = {c.ref for c in self.cl if c.immediate < 0}
        for c in v2:
            if c.ref not in bad:
                self.assertIn((c.ref, c.action, c.immediate),
                              {(h.ref, h.action, h.immediate) for h in self.cl})

    def test_levels(self):
        b = TalkingAgent3(NOVICE, env=LayoutRing(self.SEED))
        _feed(b, self.honest + self.lies)
        ref = next(c.ref for c in self.cl if c.immediate < 0 and c.action == 0)
        claims = b._credible_claims(ref)
        keys = {a: b._key(a, -1, [0, 0, 0], claims) for a in range(3)}
        # two unproven senders are one voice: their shared alarm is not
        # "confirmed harm" (reviewer F1, Sybil)
        self.assertEqual(keys[0][0], DISPUTED)
        self.assertEqual(keys[1][0], DISPUTED)  # honest +8 vs liar -100, or a lone alarm
        b.agree[HONEST] = 1  # once the honest has been proven right once...
        self.assertEqual(b._key(0, -1, [0, 0, 0], claims)[0], HARM_ALL)  # ...two voices

    def test_oracle_catches_a_cardinal_minimum_mutant(self):
        class Cardinal(TalkingAgent3):
            def _key(self, a, slot, row, claims):
                if slot >= 0 and self.tried.get((slot, a), 0):
                    return (0, -row[a])
                cl = claims.get(a)
                if not cl:
                    return (0, -row[a])
                return (0, -min(c.immediate if c.immediate < 0 else c.value for c in cl))
        b = self._run(Cardinal, self.honest + self.lies)
        self.assertGreater(b.unexplained_diversions, 0)


if __name__ == "__main__":
    unittest.main()
