"""TalkingAgent2: LINK-1's agent plus consequence, senders and trust.

Subclass of echo_wsp.link1.agent.TalkingAgent, which subclasses NEXUS-0's
Agent; neither is edited. The decision rule is LINK-1's (heard values only
for actions not tried here, never on ε turns, at most ADVICE_BUDGET
diversions per place, the gate decides), with two changes from
docs/LINK2-DESIGN.md:

* a heard action scores the immediate reward the speaker lived when that
  was negative, and the speaker's Q value otherwise;
* with several speakers, the credible one with the most net trust wins a
  (place, action); ties go to the more cautious score. Without trust
  (`trust=False`) the last one heard wins, as in LINK-1.

Trust is learned only from the novice's own experience: the first time it
executes a pair someone told it about, it compares the sign of what it got
with the sign of what each speaker said would happen.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from echo_wsp.link1.agent import _TIE_ORDER, TalkingAgent
from echo_wsp.link1.speech import referent
from echo_wsp.nexus0.constants import ACTION_APPROACH
from echo_wsp.link2.envelope import Env
from echo_wsp.link2.speech2 import Claim2, env as claim_env, read

CREDIBLE_RATIO = 3


def _trunc_mean(total: int, n: int) -> int:
    q = abs(total) // n
    return -q if total < 0 else q


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


class Testimony2:
    """What each speaker said, by referent and action. Never CAM/T/Q."""

    def __init__(self, owner: "TalkingAgent2") -> None:
        self.owner = owner
        self.by_ref: Dict[int, Dict[int, Dict[int, Tuple[int, Claim2]]]] = {}
        self.heard = 0
        self.rejected = 0
        self._clock = 0

    def add(self, c: Claim2) -> None:
        self._clock += 1
        self.by_ref.setdefault(c.ref, {}).setdefault(c.action, {})[c.sender] = (self._clock, c)
        self.heard += 1

    def answered(self, ref: int) -> bool:
        return ref in self.by_ref

    def size(self) -> int:
        return sum(len(s) for acts in self.by_ref.values() for s in acts.values())

    @staticmethod
    def score(c: Claim2) -> int:
        return c.immediate if c.immediate < 0 else c.value

    def values(self, ref: int) -> Dict[int, int]:
        out = {}
        for a, speakers in self.by_ref.get(ref, {}).items():
            pick = self.owner.pick(speakers)
            if pick is not None:
                out[a] = self.score(pick)
        return out


class TalkingAgent2(TalkingAgent):
    def __init__(self, agent_id: int, *, trust: bool = True, learn: bool = True,
                 tie: str = "cautious", **kw) -> None:
        super().__init__(agent_id, **kw)
        if tie not in ("cautious", "optimist"):
            raise ValueError("tie is cautious or optimist")
        self.trust = bool(trust)
        # Context arms only (no predictions): a ledger that never learns,
        # and ties broken towards the most optimistic score.
        self.learn = bool(learn)
        self.tie = tie
        self.testimony = Testimony2(self)
        self.lived: Dict[Tuple[int, int], List[int]] = {}  # (slot, a) -> [sum r, n]
        self.agree: Dict[int, int] = {}
        self.disagree: Dict[int, int] = {}
        self._verified: set = set()  # (sender, ref, action) already compared

    # ----------------------------------------------------------- trust
    def credible(self, sender: int) -> bool:
        d = self.disagree.get(sender, 0)
        return d == 0 or self.agree.get(sender, 0) >= CREDIBLE_RATIO * d

    def net(self, sender: int) -> int:
        return self.agree.get(sender, 0) - self.disagree.get(sender, 0)

    def pick(self, speakers: Dict[int, Tuple[int, Claim2]]) -> Optional[Claim2]:
        if not speakers:
            return None
        if not self.trust:
            return max(speakers.values(), key=lambda tc: tc[0])[1]  # last heard
        cands = [c for _t, c in speakers.values() if self.credible(c.sender)]
        if not cands:
            return None
        top = max(self.net(c.sender) for c in cands)
        best = [c for c in cands if self.net(c.sender) == top]
        if self.tie == "optimist":
            return max(best, key=lambda c: (Testimony2.score(c), -c.sender))
        return min(best, key=lambda c: (Testimony2.score(c), c.sender))

    # ---------------------------------------------------------- oracle
    def _told_raw(self, ref: int) -> Dict[int, int]:
        """LINK-2's scoring and speaker choice, rewritten from the raw claim
        log and the ledger dicts, without Testimony2.score/values or pick/
        credible/net, so that a bug in those cannot hide from the oracle."""
        out: Dict[int, int] = {}
        for a, speakers in self.testimony.by_ref.get(ref, {}).items():
            rows = []  # (heard-at, sender, score, net, credible)
            for sender, (t, c) in speakers.items():
                ag = self.agree.get(sender, 0)
                dg = self.disagree.get(sender, 0)
                sc = c.immediate if c.immediate < 0 else c.value
                rows.append((t, sender, sc, ag - dg, dg == 0 or ag >= CREDIBLE_RATIO * dg))
            if not rows:
                continue
            if not self.trust:
                out[a] = sorted(rows)[-1][2]
                continue
            ok = [r for r in rows if r[4]]
            if not ok:
                continue
            top = max(r[3] for r in ok)
            tied = [r for r in ok if r[3] == top]
            if self.tie == "optimist":
                out[a] = sorted(tied, key=lambda r: (-r[2], r[1]))[0][2]
            else:
                out[a] = sorted(tied, key=lambda r: (r[2], r[1]))[0][2]
        return out

    def _rule(self, obs: bytes, turn_i: int, greedy: bool) -> int:
        """LINK-1's oracle with LINK-2's heard scores from _told_raw."""
        n = self.n_actions
        slot = self.cam.get(obs)
        row = self.q.row(slot) if slot >= 0 else [0] * n
        a_q = self.q.select(slot, turn_i, greedy=greedy) if slot >= 0 else ACTION_APPROACH
        ref = referent(obs)
        told = self._told_raw(ref) if self.listen else {}
        if not told:
            return a_q
        if min(row) != max(row) and self.q.is_explore(slot, turn_i, greedy=greedy):
            return a_q
        if self._rule_spent.get(ref, 0) >= self.advice_budget:
            return a_q
        lived = {b for b in range(n) if slot >= 0 and self.tried.get((slot, b), 0)}
        score = [told[b] if (b in told and b not in lived) else row[b] for b in range(n)]
        top = max(score)
        if score[a_q] == top:
            return a_q
        self._rule_spent[ref] = self._rule_spent.get(ref, 0) + 1
        return next(b for b in _TIE_ORDER if b < n and score[b] == top)

    # --------------------------------------------------------- hearing
    def hear2(self, e: Env) -> None:
        c = read(e)
        if c is None:
            self.testimony.rejected += 1
            return
        if self.listen and c.sender != self.agent_id:
            self.testimony.add(c)

    # -------------------------------------------------------- speaking
    def claims2(self) -> List[Claim2]:
        out = []
        for (slot, a), n in sorted(self.tried.items()):
            ref = self.diary.get(slot)
            if ref is None or n <= 0:
                continue
            total, k = self.lived.get((slot, a), (0, 0))
            imm = _trunc_mean(total, k) if k else 0
            v = self.q.get(slot, a)
            if v == 0 and imm == 0:
                continue
            out.append(Claim2(ref=ref, action=a, value=max(-100, min(100, v)),
                              immediate=max(-100, min(100, imm)),
                              support=min(100, 10 * n), sender=self.agent_id))
        return out

    def envs(self, claims: Optional[List[Claim2]] = None, start: int = 0) -> List[Env]:
        cl = self.claims2() if claims is None else claims
        return [claim_env(c, start + i) for i, c in enumerate(cl)]

    # ---------------------------------------------------------- acting
    def turn(self, turn_i: int, greedy: bool = False) -> int:
        obs = self.observation(self.env.cell())
        ref = referent(obs)
        before = self.ret
        a = super().turn(turn_i, greedy=greedy)
        r = self.ret - before
        a = int(a) % self.n_actions
        slot = self.cam.get(obs)
        if slot >= 0:
            rec = self.lived.setdefault((slot, a), [0, 0])
            rec[0] += r
            rec[1] += 1
        if not (self.trust and self.learn):
            return a
        for sender, (_t, c) in self.testimony.by_ref.get(ref, {}).get(a, {}).items():
            key = (sender, ref, a)
            if key in self._verified:
                continue
            self._verified.add(key)
            if c.immediate == 0 and r == 0:
                continue  # a zero informs nothing
            if _sign(c.immediate) == _sign(r):
                self.agree[sender] = self.agree.get(sender, 0) + 1
            else:
                self.disagree[sender] = self.disagree.get(sender, 0) + 1
        return a

    def report(self) -> dict:
        rep = super().report()
        rep["agree"] = dict(sorted(self.agree.items()))
        rep["disagree"] = dict(sorted(self.disagree.items()))
        rep["distrusted"] = (sorted(s for s in set(self.agree) | set(self.disagree)
                                    if not self.credible(s)) if self.trust else [])
        return rep
