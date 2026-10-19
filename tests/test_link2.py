#!/usr/bin/env python3
"""LINK-2 tests. They guard docs/LINK2-DESIGN.md.

* custody: LINK-1 untouched (its pre-eval hashes still match), nothing new
  under nexus0/;
* envelope v2: 27 bytes, round trip, MAC, session binding, replay window,
  test keys only;
* phy: clean loop exact, echo room at 10 dB;
* CLAIM2: round trip and strict reader;
* agent: consequence beats value at a NOVEL with positive value, trust
  ignores a contradicted speaker, the firewall still holds (replay + oracle).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECHOAI = REPO / "echo_wsp"  # the package that holds nexus0 and the LINK code
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from echo_wsp.link1 import room
from echo_wsp.link1.agent import replay_matches
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev
from echo_wsp.link2 import phy
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.speech2 import Claim2, env as claim_env, read

KEY = ev.test_key("unit")
SESSION = ev.test_session("unit")


def _env(i=0, sender=1):
    return ev.Env(5, sender, i, bytes(range(16)))


class Custody(unittest.TestCase):
    def test_nothing_new_under_nexus0(self):
        self.assertEqual([p for p in (ECHOAI / "nexus0").rglob("*.py") if "link2" in p.parts], [])


class Envelope(unittest.TestCase):
    def test_size_and_air(self):
        raw = ev.seal(_env(), KEY, SESSION)
        self.assertEqual(len(raw), 27)
        air = ev.to_air(raw)
        self.assertEqual(len(air), 75)
        self.assertEqual(ev.from_air(air), (raw, 0))
        self.assertEqual(ev.WHITEN[:60], __import__("echo_wsp.link1.frame", fromlist=["x"]).WHITEN)

    def test_mac_session_and_replay(self):
        g = ev.Guard({1: KEY}, SESSION)
        a = ev.seal(_env(5), KEY, SESSION)
        self.assertEqual(g.admit(a), _env(5))
        self.assertIsNone(g.admit(a))  # same frame again
        self.assertIsNone(g.admit(ev.seal(_env(4), KEY, SESSION)))  # older seq
        self.assertIsNone(g.admit(ev.seal(_env(9), KEY, ev.test_session("other"))))
        self.assertIsNone(g.admit(ev.seal(_env(9), ev.test_key("x"), SESSION)))
        self.assertIsNone(g.admit(ev.seal(_env(9, sender=7), KEY, SESSION)))  # unknown sender
        self.assertEqual(g.admit(ev.seal(_env(9), KEY, SESSION)), _env(9))
        self.assertEqual(g.refused, {ev.REPLAY: 2, ev.BAD_MAC: 2, ev.UNKNOWN_SENDER: 1})

    def test_any_single_bit_flip_is_refused(self):
        raw = ev.seal(_env(1), KEY, SESSION)
        for i in range(len(raw) * 8):
            b = bytearray(raw)
            b[i // 8] ^= 1 << (i % 8)
            self.assertIsNone(ev.Guard({1: KEY}, SESSION).admit(bytes(b)))

    def test_pad_must_be_zero(self):
        raw = ev.seal(_env(), KEY, SESSION)
        nib = __import__("echo_wsp.link1.frame", fromlist=["x"]).to_nibbles(raw) + [7]
        from echo_wsp.link1 import rs
        blocks = [rs.encode(nib[b * 11:(b + 1) * 11]) for b in range(5)]
        air = [blocks[i % 5][i // 5] ^ ev.WHITEN[i] for i in range(75)]
        self.assertEqual(ev.from_air(air), (None, -1))

    def test_keys_are_declared_test_keys(self):
        self.assertEqual(ev.test_key("unit"), hashlib.sha256(
            b"LINK-2 test key, not a secret: unit").digest())


class Phy(unittest.TestCase):
    def test_clean_and_echo(self):
        raws = [ev.seal(_env(i), KEY, SESSION) for i in range(2)]
        x = [0] * 500 + phy.transmit(raws)
        self.assertEqual([h.raw for h in phy.demodulate(x)], raws)
        y = room.simulate(phy.modulate(raws[0]), snr_db=10, room="echo", seed=3)
        self.assertEqual([h.raw for h in phy.demodulate(y) if h.raw], raws[:1])
        self.assertEqual(phy.airtime_ms(), 3400)


class Speech(unittest.TestCase):
    def test_claim2_roundtrip_and_strictness(self):
        c = Claim2(ref=0x1234, action=0, value=4, immediate=-16, support=40, sender=1)
        self.assertEqual(read(claim_env(c, 3)), c)
        bad = bytearray(claim_env(c, 3).wsp)
        bad[6] = 9  # E is bytes 4..9 = V A D C U B: D set, not a CLAIM2
        self.assertIsNone(read(ev.Env(5, 1, 3, bytes(bad))))
        self.assertIsNone(read(ev.Env(5, 2, 3, claim_env(c, 3).wsp)))  # generator spoof


class Agent(unittest.TestCase):
    def _vet(self, seed):
        a = TalkingAgent2(1, env=LayoutRing(seed))
        a.run(256)
        return a

    def test_consequence_fixes_link1_failure_world(self):
        # world 1012: LINK-1's veteran said approach +4 at the NOVEL cell
        a = self._vet(1012)
        cl = a.claims2()
        def novice(claims):
            b = TalkingAgent2(2, env=LayoutRing(1012), trust=False, audit=True)
            for e in a.envs(claims):
                b.hear2(e)
            b.run(256)
            return b
        t1 = novice([Claim2(c.ref, c.action, c.value, 0, c.support, c.sender)
                     for c in cl if c.value])
        t2 = novice(cl)
        self.assertEqual(t1.first_harm, 1)
        self.assertEqual(t2.first_harm, 0)
        for b in (t1, t2):
            self.assertEqual(b.unexplained_diversions, 0)
            self.assertTrue(replay_matches(b, LayoutRing(1012)))

    def test_trust_distrusts_an_insider_liar(self):
        a = self._vet(3)
        cl = a.claims2()
        lies = [Claim2(c.ref, c.action, -c.value, -c.immediate, c.support, 3) for c in cl]
        b = TalkingAgent2(2, env=LayoutRing(3), trust=True, audit=True)
        for e in a.envs(cl) + a.envs(lies):
            b.hear2(e)
        b.run(256)
        self.assertIn(3, b.report()["distrusted"])
        self.assertNotIn(1, b.report()["distrusted"])
        self.assertEqual(b.first_harm, 0)
        self.assertEqual(b.unexplained_diversions, 0)
        self.assertTrue(replay_matches(b, LayoutRing(3)))

    def test_oracle_catches_a_scoring_mutant(self):
        from echo_wsp.link2.agent2 import Testimony2
        a = self._vet(1012)
        orig = Testimony2.__dict__["score"]
        try:
            Testimony2.score = staticmethod(lambda c: c.value)  # consequence ignored
            b = TalkingAgent2(2, env=LayoutRing(1012), trust=False)
            for e in a.envs():
                b.hear2(e)
            b.run(256)
        finally:
            Testimony2.score = orig
        self.assertGreater(b.unexplained_diversions, 0)

    def test_oracle_catches_a_speaker_choice_mutant(self):
        a = self._vet(1012)
        cl = a.claims2()
        lies = [Claim2(c.ref, c.action, -c.value, -c.immediate, c.support, 3) for c in cl]

        class Gullible(TalkingAgent2):
            def pick(self, speakers):  # always the liar
                return next((c for _t, c in speakers.values() if c.sender == 3), None)
        b = Gullible(2, env=LayoutRing(1012), trust=True)
        for e in a.envs(cl) + a.envs(lies):
            b.hear2(e)
        b.run(256)
        self.assertGreater(b.unexplained_diversions, 0)

    def test_naive_last_heard_liar_hurts(self):
        a = self._vet(3)
        cl = a.claims2()
        lies = [Claim2(c.ref, c.action, -c.value, -c.immediate, c.support, 3) for c in cl]
        b = TalkingAgent2(2, env=LayoutRing(3), trust=False)
        for e in a.envs(cl) + a.envs(lies):
            b.hear2(e)
        b.run(256)
        self.assertGreater(b.first_harm, 0)


if __name__ == "__main__":
    unittest.main()
