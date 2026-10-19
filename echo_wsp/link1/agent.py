"""A NEXUS-0 agent that can tell and be told. Subclass, never a fork.

Everything that decides — CAM, T, Q, the gate, ε — is the imported
`echo_wsp.nexus0.loop.Agent`, untouched. This class adds three things:

1. a diary of where it has stood (slot -> observation postcard), so it can
   speak only about places it lived;
2. a `Testimony` store, separate from CAM/T/Q, for what it was told;
3. one override, `_propose`, which lets heard values stand in for the
   zeros of actions the agent has **not** tried at this place, outside the
   periodic exploration turns, at most `ADVICE_BUDGET` times per place.

The gate still runs on whatever `_propose` returns. Testimony is never
written into CAM, T or Q: `replay_matches` proves it after a run (a deaf
twin fed the same proposals must end byte-identical), and `audit=True`
adds a per-turn check of which Q/T cells moved.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Optional, Tuple

from echo_wsp.link1.frame import Frame
from echo_wsp.link1.speech import (
    Claim,
    ask_frame,
    claim_frame,
    read_ask,
    read_claim,
    read_unknown,
    referent,
    unknown_frame,
)
from echo_wsp.nexus0.constants import (
    ACTION_APPROACH,
    ACTION_AVOID,
    ACTION_REL,
    ACTION_WAIT,
)
from echo_wsp.nexus0.loop import Agent

ADVICE_BUDGET = 4
# Ties among borrowed scores walk rather than stand: approach, avoid, wait.
_TIE_ORDER = (ACTION_APPROACH, ACTION_AVOID, ACTION_WAIT)


class Testimony:
    """What others said, by referent. Not a fact table and not a policy."""

    def __init__(self) -> None:
        # ref -> action -> (value, support, sender)
        self.by_ref: Dict[int, Dict[int, Tuple[int, int, int]]] = {}
        self.unknown: Dict[int, set] = {}
        self.heard = 0
        self.rejected = 0

    def add_claim(self, c: Claim) -> None:
        self.by_ref.setdefault(c.ref, {})[c.action] = (c.value, c.support, c.sender)
        self.heard += 1

    def add_unknown(self, ref: int, sender: int) -> None:
        self.unknown.setdefault(ref, set()).add(sender)
        self.heard += 1

    def values(self, ref: int) -> Dict[int, int]:
        return {a: v for a, (v, _c, _s) in self.by_ref.get(ref, {}).items()}

    def answered(self, ref: int) -> bool:
        return ref in self.by_ref or ref in self.unknown

    def size(self) -> int:
        return sum(len(v) for v in self.by_ref.values())


class TalkingAgent(Agent):
    def __init__(self, agent_id: int, *, listen: bool = True,
                 advice_budget: int = ADVICE_BUDGET, audit: bool = False,
                 **kw) -> None:
        kw.setdefault("ask", False)  # NEXUS-3's oracle is another channel
        super().__init__(**kw)
        if type(agent_id) is not int or not 0 <= agent_id <= 255:
            raise ValueError("agent_id must be a byte")
        if self.cortex_enabled:
            raise ValueError("LINK-1 runs with the cortex off")
        if (self.plan_depth or self.escalate_enabled or self.evidence_budget
                or self.q.explore_flat or self.survival_enabled):
            # The independent diversion check in turn() recomputes Q's own
            # proposal with q.select; that is exact only on this path.
            raise ValueError("LINK-1 uses NEXUS-0's plain proposal path")
        self.agent_id = agent_id
        self.listen = bool(listen)
        self.advice_budget = int(advice_budget)
        self.audit = bool(audit)
        self.testimony = Testimony()
        self.diary: Dict[int, int] = {}  # slot -> referent of what I saw there
        self.tried: Dict[Tuple[int, int], int] = {}  # (slot, action) -> own tries
        self.advice_spent: Dict[int, int] = {}  # referent -> diversions
        self.asked: set = set()  # referents I already asked about
        self.diversions = 0
        # Turns whose proposal differs from what the contract's rule allows,
        # recomputed in turn() by _rule, outside _propose. Must stay 0.
        self.unexplained_diversions = 0
        self.proposals: List[int] = []  # what went to the gate, per turn
        self._rule_spent: Dict[int, int] = {}  # the oracle's own budget ledger
        self.foreign_q_writes = 0
        self.foreign_t_writes = 0
        self.foreign_cam_allocs = 0
        self.harm = 0
        self.ret = 0
        self.first_seen: Dict[int, Tuple[int, int]] = {}  # ref -> (action, r)
        self.first_harm = 0
        self._cur_ref: Optional[int] = None
        self._seq = 0

    # ------------------------------------------------------------ hearing
    def hear(self, f: Frame) -> Optional[List[Frame]]:
        """Take one frame off a link. Returns reply frames (to an ASK) or None.

        Only the testimony store moves here; CAM, T and Q are not touched.
        """
        c = read_claim(f)
        if c is not None:
            if self.listen and f.sender != self.agent_id:
                self.testimony.add_claim(c)
            return None
        ref = read_unknown(f)
        if ref is not None:
            if self.listen:
                self.testimony.add_unknown(ref, f.sender)
            return None
        ref = read_ask(f)
        if ref is not None and f.sender != self.agent_id:
            return self.answer(ref)
        if f.act not in (0, 4):  # HELLO and BYE carry nothing to store
            self.testimony.rejected += 1
        return None

    # ----------------------------------------------------------- speaking
    def _next_seq(self) -> int:
        s = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return s

    def claims(self, include_zero: bool = False) -> List[Claim]:
        """Only pairs this agent executed itself. Sorted, deterministic."""
        out = []
        for (slot, a), n in sorted(self.tried.items()):
            ref = self.diary.get(slot)
            if ref is None or n <= 0:
                continue
            v = self.q.get(slot, a)
            if v == 0 and not include_zero:
                continue
            out.append(Claim(ref=ref, action=a, value=max(-100, min(100, v)),
                             support=min(100, 10 * n), sender=self.agent_id))
        return out

    def broadcast(self) -> List[Frame]:
        return [claim_frame(c, self._next_seq()) for c in self.claims()]

    def answer(self, ref: int) -> List[Frame]:
        """What I lived at `ref`: non-zero values, else one zero, else UNKNOWN.

        A zero says nothing a listener does not already assume, so it is
        sent only to say "I was there and nothing happened".
        """
        lived = [c for c in self.claims(include_zero=True) if c.ref == ref]
        if not lived:
            return [unknown_frame(ref, self.agent_id, self._next_seq())]
        cl = [c for c in lived if c.value != 0]
        if not cl:
            cl = [max(lived, key=lambda c: (c.support, -c.action))]
        return [claim_frame(c, self._next_seq()) for c in cl]

    def question_here(self) -> Optional[Frame]:
        """ASK about the place I stand on, if it looks unusual and I don't know.

        Unusual is read off my own observation: any packet whose relation is
        not the plain OBSERVAR of an empty cell. Asking about every empty
        cell would cost a postcard per step and buy nothing.
        """
        cell = self.env.cell()
        obs = self.observation(cell)
        if obs[1] == ACTION_REL[ACTION_WAIT]:  # OBSERVAR -> AQUI: empty
            return None
        ref = referent(obs)
        if self.testimony.answered(ref) or ref in self.asked:
            return None
        slot = self.cam.get(obs)
        if slot >= 0 and any(self.tried.get((slot, a), 0)
                             for a in range(self.n_actions)):
            return None
        # Asked once. If the question or its answer is lost on the air the
        # novice goes on with what it knows instead of asking every turn.
        self.asked.add(ref)
        return ask_frame(ref, self.agent_id, self._next_seq())

    # ------------------------------------------------------------ acting
    def _propose(self, slot: int, turn_i: int, greedy: bool = False) -> int:
        a0 = super()._propose(slot, turn_i, greedy=greedy)
        if not self.listen or self._cur_ref is None:
            return a0
        told = self.testimony.values(self._cur_ref)
        if not told:
            return a0
        row = self.q.row(slot)
        if not self.q.flat(row) and self.q.is_explore(slot, turn_i, greedy=greedy):
            return a0  # a periodic ε turn is the agent's own verification
        if self.advice_spent.get(self._cur_ref, 0) >= self.advice_budget:
            return a0
        # Heard values stand in only for actions I have not tried here.
        borrowed = {a for a in range(self.n_actions)
                    if self.tried.get((slot, a), 0) == 0 and a in told}
        score = {a: (told[a] if a in borrowed else row[a])
                 for a in range(self.n_actions)}
        best = max(score.values())
        if score[a0] == best:
            return a0
        for a in _TIE_ORDER:
            if a < self.n_actions and score[a] == best:
                self.advice_spent[self._cur_ref] = (
                    self.advice_spent.get(self._cur_ref, 0) + 1)
                self.diversions += 1
                return a
        return a0

    def _rule(self, obs: bytes, turn_i: int, greedy: bool) -> int:
        """Oracle for the proposal LINK-1 allows, from the state before a turn.

        Q's own choice, unless something heard about an action not yet tried
        here outranks it, outside ε verification turns, within budget.
        """
        n = self.n_actions
        slot = self.cam.get(obs)
        row = self.q.row(slot) if slot >= 0 else [0] * n
        if slot >= 0:
            a_q = self.q.select(slot, turn_i, greedy=greedy)
        else:
            a_q = ACTION_APPROACH  # a never-seen place: flat row, explores forward
        ref = referent(obs)
        told = self.testimony.values(ref) if self.listen else {}
        if not told:
            return a_q
        flat = min(row) == max(row)
        if not flat and self.q.is_explore(slot, turn_i, greedy=greedy):
            return a_q
        # Its own budget ledger: if it read advice_spent, which _propose
        # writes, a _propose that never paid would never run out.
        if self._rule_spent.get(ref, 0) >= self.advice_budget:
            return a_q
        lived = {b for b in range(n) if slot >= 0 and self.tried.get((slot, b), 0)}
        score = [told[b] if (b in told and b not in lived) else row[b]
                 for b in range(n)]
        top = max(score)
        if score[a_q] == top:
            return a_q
        self._rule_spent[ref] = self._rule_spent.get(ref, 0) + 1
        return next(b for b in _TIE_ORDER if b < n and score[b] == top)

    def turn(self, turn_i: int, greedy: bool = False) -> int:
        cell = self.env.cell()
        obs = self.observation(cell)
        self._cur_ref = referent(obs)
        if self.audit:
            q_before = [row[:] for row in self.q.q]
            t_before = [row[:] for row in self.t.n]
            cam_before = set(self.cam.occupied_slots())
        r_before = getattr(self.env, "ret", None)
        first = self._cur_ref not in self.first_seen
        # The contract's rule, recomputed from the pre-turn state by code
        # that does not call _propose: a faulty _propose cannot hide.
        expected = self._rule(obs, turn_i, greedy)
        a = super().turn(turn_i, greedy=greedy)
        a_prop = int(self.last_proposed_action) % self.n_actions
        self.proposals.append(a_prop)
        if a_prop != expected:
            self.unexplained_diversions += 1
        slot = self.cam.get(obs)
        if slot >= 0:
            self.diary[slot] = self._cur_ref
            key = (slot, int(a) % self.n_actions)
            self.tried[key] = self.tried.get(key, 0) + 1
        if r_before is not None:
            r = self.env.ret - r_before
            self.ret += r
            if r < 0:
                self.harm += 1
            if first:
                # The first lesson at a place: what did standing here for the
                # first time cost? Testimony can only ever save this one.
                self.first_seen[self._cur_ref] = (int(a) % self.n_actions, int(r))
                if r < 0:
                    self.first_harm += 1
        if self.audit:
            nxt = self.observation(self.env.cell())
            slot_n = self.cam.get(nxt)
            own_q = {(slot, int(a) % self.n_actions)}
            for s, row in enumerate(self.q.q):
                if row != q_before[s]:
                    for j in range(self.n_actions):
                        if row[j] != q_before[s][j] and (s, j) not in own_q:
                            self.foreign_q_writes += 1
            for s, row in enumerate(self.t.n):
                if row != t_before[s]:
                    for j in range(self.n_actions):
                        if row[j] != t_before[s][j] and (s, j) not in own_q:
                            self.foreign_t_writes += 1
            new = set(self.cam.occupied_slots()) - cam_before
            if new - {slot, slot_n}:
                self.foreign_cam_allocs += len(new - {slot, slot_n})
        self._cur_ref = None
        return a

    def report(self) -> dict:
        m = self.metrics.as_dict()
        return {
            "agent": self.agent_id,
            "harm": self.harm,
            "first_harm": self.first_harm,
            "places_visited": len(self.first_seen),
            "return": self.ret,
            "turns": m["turns"],
            "diversions": self.diversions,
            "unexplained_diversions": self.unexplained_diversions,
            "testimony_heard": self.testimony.heard,
            "testimony_rejected": self.testimony.rejected,
            "testimony_size": self.testimony.size(),
            "foreign_q_writes": self.foreign_q_writes,
            "foreign_t_writes": self.foreign_t_writes,
            "foreign_cam_allocs": self.foreign_cam_allocs,
            "false_facts": m["false_facts"],
            "destroyed": m["destroyed"],
            "cortex_calls": m["cortex_calls"],
        }


def core_digest(agent: Agent) -> str:
    """SHA-256 of everything that is memory or policy: CAM, T and Q.

    Not the testimony store, not the diary, not the counters.
    """
    h = hashlib.sha256()
    h.update(repr(agent.q.q).encode())
    t = agent.t
    h.update(repr((t.pred, t.n, t.alt, t.alt_n, t.conflicts, t.inv,
                   t.inv_dropped)).encode())
    cam = agent.cam
    h.update(repr((cam.used, cam.destroyed, sorted(cam.key_index.items()))).encode())
    for sl in cam.slot:
        h.update(repr((sl.wsp, sl.vertex, sl.latency, sl.hits, sl.occupied,
                       sl.flags, sl.persona, sl.E, sl.weight, sl.has_fact,
                       sl.extract, sl.source, sl.label, sl.kind, sl.see,
                       sl.keys)).encode())
    return h.hexdigest()


class _Replayer(TalkingAgent):
    """Deaf twin: hears nothing, and hands the gate a recorded proposal."""

    def __init__(self, script: List[int], **kw) -> None:
        super().__init__(0, listen=False, **kw)
        self.script = list(script)

    def _propose(self, slot: int, turn_i: int, greedy: bool = False) -> int:
        return self.script[turn_i]


def replay_matches(listener: TalkingAgent, env) -> bool:
    """P3's real check. Give a deaf twin the listener's proposals, turn by
    turn, in a fresh copy of the same world. If testimony never reached
    CAM, T or Q by any path, the twin ends byte-identical; if it leaked
    anywhere (while hearing, in a turn, between turns) the digests differ.
    """
    twin = _Replayer(listener.proposals, env=env)
    twin.env.reset()
    twin.q.reset_traces()
    twin.clear_context()
    for t in range(len(listener.proposals)):
        twin.turn(t)
    return core_digest(twin) == core_digest(listener)


def deliver(agent: TalkingAgent, frames: Iterable[Frame]) -> List[Frame]:
    replies: List[Frame] = []
    for f in frames:
        r = agent.hear(f)
        if r:
            replies.extend(r)
    return replies
