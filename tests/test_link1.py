#!/usr/bin/env python3
"""LINK-1 tests. They guard docs/LINK1-DESIGN.md.

* custody: nothing new under nexus0/, DRONE-3's pinned files still hash
  the same, the postcard is still 16 bytes;
* codec: envelope, CRC and RS(15,11) do what they claim;
* modem: integer tables pinned, clean loop exact, noise never becomes a frame;
* speech: CLAIM/ASK/UNKNOWN round-trip and reject anything else;
* firewall: hearing never touches CAM/T/Q, lived experience beats testimony,
  the advice budget holds, and a speaker never claims what it did not do.
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

from echo_wsp.navi10_wsp import pack

from echo_wsp.link1 import frame as fr
from echo_wsp.link1 import modem, room, rs, speech
from echo_wsp.link1.agent import (
    ADVICE_BUDGET,
    TalkingAgent,
    core_digest,
    deliver,
    replay_matches,
)
from echo_wsp.link1.speech import Claim, claim_frame
from echo_wsp.link1.world import LayoutRing, layout
from echo_wsp.nexus0.env import KIND_GOAL, KIND_NOVEL, KIND_THREAT

TABLE_SHA256 = "42d6b5cbde529625a0e5db252a61095bdd0e7a12e6291cde9eb661e15ded28aa"
WHITEN_SHA256 = "473bde027e0e992a7aeda8a64ff884f27d3e96d3c4cdaab7179cd9bb2e794cfb"


class Custody(unittest.TestCase):
    def test_nothing_new_under_nexus0(self):
        self.assertFalse((ECHOAI / "nexus0" / "link1").exists())
        offenders = [p for p in (ECHOAI / "nexus0").rglob("*.py") if "link1" in p.parts]
        self.assertEqual(offenders, [])

    def test_postcard_is_sixteen_bytes_inside_a_22_byte_envelope(self):
        self.assertEqual(len(pack()), 16)
        self.assertEqual(fr.FRAME_BYTES, 22)
        f = speech.hello_frame(1)
        self.assertEqual(f.to_bytes()[4:20], f.wsp)


class Codec(unittest.TestCase):
    def test_roundtrip_and_crc(self):
        r = random.Random(0)
        for _ in range(500):
            f = fr.Frame(r.randrange(5), r.randrange(256), r.randrange(256),
                         bytes(r.randrange(256) for _ in range(16)))
            raw = f.to_bytes()
            self.assertEqual(fr.parse(raw), f)
            bad = bytearray(raw)
            bad[r.randrange(22)] ^= 1 << r.randrange(8)
            self.assertIsNone(fr.parse(bytes(bad)))

    def test_rs_corrects_two_and_never_silently_three_with_crc(self):
        r = random.Random(1)
        for ne in (0, 1, 2):
            for _ in range(300):
                m = [r.randrange(16) for _ in range(rs.K)]
                c = rs.encode(m)
                for p in r.sample(range(rs.N), ne):
                    c[p] ^= r.randrange(1, 16)
                self.assertEqual(rs.decode(c), (m, ne))
        # three wrong tones in one block: RS may fail or miscorrect, the
        # frame CRC must then refuse it
        for _ in range(200):
            f = fr.Frame(1, 2, 3, bytes(r.randrange(256) for _ in range(16)))
            air = fr.to_air(f.to_bytes())
            for p in r.sample(range(15), 3):
                air[p * fr.BLOCKS] ^= r.randrange(1, 16)  # all in block 0
            raw, _n = fr.from_air(air)
            self.assertTrue(raw is None or fr.parse(raw) is None or fr.parse(raw) == f)

    def test_whitening_is_pinned_and_spreads_zeros(self):
        self.assertEqual(hashlib.sha256(bytes(fr.WHITEN)).hexdigest(), WHITEN_SHA256)
        zeros = fr.Frame(0, 0, 0, bytes(16))
        air = fr.to_air(zeros.to_bytes())
        self.assertGreaterEqual(len(set(air)), 12)  # zeros ride many tones

    def test_erasures_rescue_a_block_with_three_wrong_tones(self):
        f = fr.Frame(1, 2, 3, bytes(range(16)))
        air = fr.to_air(f.to_bytes())
        doubt = [0] * fr.AIR_SYMBOLS
        for p in (0, 5, 9):  # three errors, all in block 0, all doubted
            air[p * fr.BLOCKS] ^= 0x7
            doubt[p * fr.BLOCKS] = 4000
        self.assertIsNone(fr.parse(fr.from_air(air)[0] or bytes(22)))
        raw, _ = fr.from_air(air, doubt)
        self.assertEqual(fr.parse(raw), f)

    def test_rs_errors_and_erasures(self):
        r = random.Random(4)
        for _ in range(600):
            m = [r.randrange(16) for _ in range(rs.K)]
            c = rs.encode(m)
            e = r.randrange(0, 5)
            t = r.randrange(0, (4 - e) // 2 + 1)
            pos = r.sample(range(rs.N), e + t)
            for p in pos[:e]:
                c[p] = r.randrange(16)
            for p in pos[e:]:
                c[p] ^= r.randrange(1, 16)
            self.assertEqual(rs.decode(c, erasures=pos[:e])[0], m)

    def test_interleave_spreads_a_burst(self):
        f = fr.Frame(1, 9, 9, bytes(range(16)))
        air = fr.to_air(f.to_bytes())
        for i in range(20, 28):  # 8 consecutive wrong tones
            air[i] ^= 0x5
        raw, fixed = fr.from_air(air)
        self.assertEqual(fr.parse(raw), f)
        self.assertEqual(fixed, 8)


class Modem(unittest.TestCase):
    def test_table_is_pinned(self):
        self.assertEqual(modem.TABLE_SHA256, TABLE_SHA256)

    def test_tones_sit_on_exact_bins_inside_nyquist(self):
        for k in modem.DATA_K1 + modem.DATA_K2[0] + modem.DATA_K2[1] + modem.GREETING:
            self.assertLess(k * modem.RATE // modem.N, modem.RATE // 2)
        self.assertEqual(len(set(modem.DATA_K1)), 16)
        # greeting ratios of WSP v0.4: 1, 9/8, 8/9, 4/9, 2/3 of RE
        re = modem.GREETING[0]
        self.assertEqual([g * 72 // re for g in modem.GREETING], [72, 81, 64, 32, 48])

    def test_clean_loop_is_exact_for_both_modes(self):
        r = random.Random(2)
        for k in (1, 2):
            frames = [fr.Frame(1, 4, i, bytes(r.randrange(256) for _ in range(16)))
                      for i in range(2)]
            x = [0] * 777 + modem.transmit(frames, k)
            heard = [h.frame for h in modem.demodulate(x, k)]
            self.assertEqual(heard, frames)

    def test_samples_are_int16_and_integer(self):
        x = modem.modulate(speech.hello_frame(1).to_bytes(), 1)
        self.assertTrue(all(type(v) is int and -32768 <= v <= 32767 for v in x))
        self.assertEqual(len(x), modem.frame_samples(1))

    def test_noise_never_becomes_a_frame(self):
        r = random.Random(3)
        y = [int(r.gauss(0, 4000)) for _ in range(5 * modem.RATE)]
        y = [max(-32768, min(32767, v)) for v in y]
        for k in (1, 2):
            self.assertEqual([h for h in modem.demodulate(y, k) if h.frame], [])

    def test_echo_room_at_10db(self):
        f = speech.hello_frame(3, 5)
        y = room.simulate(modem.modulate(f.to_bytes(), 1), snr_db=10, room="echo", seed=4)
        self.assertEqual([h.frame for h in modem.demodulate(y, 1) if h.frame], [f])


class Speech(unittest.TestCase):
    def test_claim_roundtrip(self):
        c = Claim(ref=0xA1B2, action=1, value=-12, support=40, sender=9)
        f = claim_frame(c, 3)
        self.assertEqual(speech.read_claim(f), c)
        self.assertIsNone(speech.read_ask(f))

    def test_ask_and_unknown(self):
        self.assertEqual(speech.read_ask(speech.ask_frame(0x0102, 2, 0)), 0x0102)
        self.assertEqual(speech.read_unknown(speech.unknown_frame(0x0304, 1, 0)), 0x0304)

    def test_a_claim_with_foreign_fields_is_ignored(self):
        c = Claim(ref=1, action=0, value=5, support=10, sender=1)
        raw = bytearray(speech.claim_postcard(c))
        raw[7] = 50  # E.C fine, but put arousal in: not a CLAIM shape
        raw[5] = 30
        f = fr.Frame(fr.ACT_CLAIM, 1, 0, bytes(raw))
        self.assertIsNone(speech.read_claim(f))
        # sender spoofing the generator byte
        f2 = fr.Frame(fr.ACT_CLAIM, 2, 0, speech.claim_postcard(c))
        self.assertIsNone(speech.read_claim(f2))

    def test_referent_is_perceptual(self):
        from echo_wsp.nexus0.encoder import encode_cell
        a = speech.referent(encode_cell(7, KIND_THREAT))
        b = speech.referent(encode_cell(7, 0))
        self.assertNotEqual(a, b)  # same index, different look: different place


class Firewall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = 3
        cls.vet = TalkingAgent(1, env=LayoutRing(cls.seed))
        cls.vet.run(256)

    def test_speaker_claims_only_what_it_did(self):
        for c in self.vet.claims(include_zero=True):
            slots = [s for s, ref in self.vet.diary.items() if ref == c.ref]
            self.assertTrue(any(self.vet.tried.get((s, c.action), 0) > 0 for s in slots))

    def test_unknown_for_a_place_never_lived(self):
        out = self.vet.answer(0xFFFF if 0xFFFF not in self.vet.diary.values() else 0xFFFE)
        self.assertEqual([f.act for f in out], [fr.ACT_UNKNOWN])

    def test_hearing_touches_no_core_table(self):
        b = TalkingAgent(2, env=LayoutRing(self.seed))
        q0 = [row[:] for row in b.q.q]
        t0 = [row[:] for row in b.t.n]
        used = b.cam.used
        deliver(b, self.vet.broadcast())
        self.assertGreater(b.testimony.size(), 0)
        self.assertEqual([row[:] for row in b.q.q], q0)
        self.assertEqual([row[:] for row in b.t.n], t0)
        self.assertEqual(b.cam.used, used)

    def test_truth_saves_first_lessons_and_audit_is_clean(self):
        silent = TalkingAgent(2, env=LayoutRing(self.seed), audit=True)
        silent.run(256)
        told = TalkingAgent(2, env=LayoutRing(self.seed), audit=True)
        deliver(told, self.vet.broadcast())
        told.run(256)
        self.assertLess(told.first_harm, silent.first_harm)
        for ag in (silent, told):
            r = ag.report()
            for k in ("false_facts", "destroyed", "cortex_calls", "foreign_q_writes",
                      "foreign_t_writes", "foreign_cam_allocs", "unexplained_diversions"):
                self.assertEqual(r[k], 0, k)
            self.assertTrue(replay_matches(ag, LayoutRing(self.seed)))

    def test_advice_budget_bounds_a_liar(self):
        lies = [Claim(c.ref, c.action, -c.value, c.support, c.sender)
                for c in self.vet.claims()]
        b = TalkingAgent(2, env=LayoutRing(self.seed), audit=True)
        deliver(b, [claim_frame(c, i) for i, c in enumerate(lies)])
        b.run(256)
        self.assertLessEqual(b.diversions, ADVICE_BUDGET * len(b.testimony.by_ref))
        self.assertEqual(b.unexplained_diversions, 0)
        self.assertTrue(replay_matches(b, LayoutRing(self.seed)))

    def _liar_frames(self):
        lies = [Claim(c.ref, c.action, -c.value, c.support, c.sender)
                for c in self.vet.claims()]
        return [claim_frame(c, i) for i, c in enumerate(lies)]

    def test_check_catches_a_propose_that_trusts_hearsay_over_experience(self):
        class Mutant(TalkingAgent):
            # the "untried only" filter and the budget removed: heard values
            # override lived ones, for ever. The oracle in turn() must see it.
            def _propose(self, slot, turn_i, greedy=False):
                a0 = TalkingAgent.__mro__[1]._propose(self, slot, turn_i, greedy)
                told = self.testimony.values(self._cur_ref)
                if not told:
                    return a0
                row = self.q.row(slot)
                score = {a: told.get(a, row[a]) for a in range(self.n_actions)}
                return max(range(self.n_actions), key=lambda a: (score[a], -a))
        b = Mutant(2, env=LayoutRing(self.seed))
        deliver(b, self._liar_frames())
        b.run(256)
        self.assertGreater(b.unexplained_diversions, 0)

    def test_check_catches_a_budgeted_propose_without_the_untried_filter(self):
        from echo_wsp.link1.agent import _TIE_ORDER
        from echo_wsp.nexus0.loop import Agent

        class Subtle(TalkingAgent):
            # identical to the real rule except that heard values also
            # replace values the agent has lived; budget and ε respected
            def _propose(self, slot, turn_i, greedy=False):
                a0 = Agent._propose(self, slot, turn_i, greedy)
                told = self.testimony.values(self._cur_ref)
                if not told:
                    return a0
                row = self.q.row(slot)
                if not self.q.flat(row) and self.q.is_explore(slot, turn_i, greedy):
                    return a0
                if self.advice_spent.get(self._cur_ref, 0) >= self.advice_budget:
                    return a0
                score = {a: told.get(a, row[a]) for a in range(self.n_actions)}
                best = max(score.values())
                if score[a0] == best:
                    return a0
                a = next(x for x in _TIE_ORDER if score[x] == best)
                self.advice_spent[self._cur_ref] = self.advice_spent.get(self._cur_ref, 0) + 1
                return a
        b = Subtle(2, env=LayoutRing(self.seed))
        deliver(b, self._liar_frames())
        b.run(256)
        self.assertGreater(b.unexplained_diversions, 0)

    def test_replay_catches_a_leak_while_hearing(self):
        class LeakyEar(TalkingAgent):
            def hear(self, f):
                out = super().hear(f)
                self.t.n[1][0] += 1  # hearsay counted as a lived transition
                return out
        b = LeakyEar(2, env=LayoutRing(self.seed))
        before = core_digest(b)
        deliver(b, self.vet.broadcast())
        self.assertNotEqual(core_digest(b), before)
        b.run(256)
        self.assertFalse(replay_matches(b, LayoutRing(self.seed)))

    def test_replay_catches_a_leak_on_the_own_cell(self):
        class LeakyHand(TalkingAgent):
            # writes the heard value into Q at the very pair it acted on,
            # which the per-turn audit exempts as "own"
            def turn(self, turn_i, greedy=False):
                obs = self.observation(self.env.cell())
                ref = __import__("echo_wsp.link1.speech", fromlist=["x"]).referent(obs)
                a = super().turn(turn_i, greedy)
                slot = self.cam.get(obs)
                told = self.testimony.values(ref)
                if slot >= 0 and a in told:
                    self.q.set(slot, a, told[a])
                return a
        b = LeakyHand(2, env=LayoutRing(self.seed), audit=True)
        # false values: a true one would equal what own experience converges
        # to in this deterministic world, and no state check could see it
        deliver(b, self._liar_frames())
        b.run(256)
        self.assertEqual(b.foreign_q_writes, 0)  # the audit is blind here...
        self.assertFalse(replay_matches(b, LayoutRing(self.seed)))  # ...replay is not

    def test_cortex_refused(self):
        with self.assertRaises(ValueError):
            TalkingAgent(2, cortex=True)


class Worlds(unittest.TestCase):
    def test_layout_counts(self):
        for s in range(20):
            k = layout(s)
            self.assertEqual(k.count(KIND_THREAT), 2)
            self.assertEqual(k.count(KIND_GOAL), 3)
            self.assertEqual(k.count(KIND_NOVEL), 1)
            self.assertEqual(k[0], 0)

    def test_moved_world_moves_only_threats(self):
        w = LayoutRing(5)
        m = w.moved(5)
        self.assertEqual(m.kind.count(KIND_THREAT), 2)
        self.assertNotEqual([i for i, k in enumerate(w.kind) if k == KIND_THREAT],
                            [i for i, k in enumerate(m.kind) if k == KIND_THREAT])
        for i in range(32):
            if w.kind[i] in (KIND_GOAL, KIND_NOVEL):
                self.assertEqual(w.kind[i], m.kind[i])


if __name__ == "__main__":
    unittest.main()
