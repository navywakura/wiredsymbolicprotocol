"""TalkingAgent3: LINK-2's agent with a lexicographic risk rule and a
differential trust ledger.

What changes against LINK-2 (docs/LINK3-DESIGN.md):

* Decision. For each action, a risk level from the credible claims about
  it (consequence saturated to harm / safe): 0 all safe, 1 nobody spoke,
  2 disputed or a lone alarm, 3 harm confirmed by two or more. An action already tried
  here enters by what the novice lived (0 or 3). Lowest level wins; within
  a level, highest value. In a disputed tie Q's default gets no preference
  and the order is avoid, wait, approach.
* Trust. On executing a pair someone spoke about, whoever got the class
  wrong loses credit always; whoever got it right gains credit only if
  someone else said the opposite.

Unchanged: only untried actions borrow, ε turns untouched, at most
ADVICE_BUDGET diversions per place, the gate decides, CAM/T/Q never see
testimony. `_rule` is a separately written oracle of the same contract.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from echo_wsp.link1.agent import TalkingAgent
from echo_wsp.link1.speech import referent
from echo_wsp.link2.agent2 import CREDIBLE_RATIO, TalkingAgent2
from echo_wsp.link2.speech2 import Claim2
from echo_wsp.nexus0.constants import ACTION_APPROACH, ACTION_AVOID, ACTION_WAIT
from echo_wsp.nexus0.loop import Agent

SAFE_ALL, UNKNOWN, DISPUTED, HARM_ALL = 0, 1, 2, 3
CALM_ORDER = (ACTION_APPROACH, ACTION_AVOID, ACTION_WAIT)
SCEPTIC_ORDER = (ACTION_AVOID, ACTION_WAIT, ACTION_APPROACH)


class TalkingAgent3(TalkingAgent2):
    def __init__(self, agent_id: int, **kw) -> None:
        kw.setdefault("trust", True)
        super().__init__(agent_id, **kw)
        if not self.trust:
            raise ValueError("LINK-3 always weighs speakers")

    # ---------------------------------------------------------- claims
    def _credible_claims(self, ref: int) -> Dict[int, List[Claim2]]:
        out: Dict[int, List[Claim2]] = {}
        for a, speakers in self.testimony.by_ref.get(ref, {}).items():
            cl = [c for _t, c in speakers.values() if self.credible(c.sender)]
            if cl:
                out[a] = cl
        return out

    def _key(self, a: int, slot: int, row: List[int],
             claims: Dict[int, List[Claim2]]) -> Tuple[int, int]:
        if slot >= 0 and self.tried.get((slot, a), 0):
            total, n = self.lived.get((slot, a), (0, 0))
            return (HARM_ALL if total < 0 else SAFE_ALL, -row[a])
        cl = claims.get(a)
        if not cl:
            return (UNKNOWN, -row[a])
        harm = [c.immediate < 0 for c in cl]
        # Voices, not keys: senders not yet proven right in a dispute count
        # together as one voice, so fresh identities cannot confirm harm.
        voices = len({c.sender for c in cl if self.agree.get(c.sender, 0) > 0}) + \
            (1 if any(self.agree.get(c.sender, 0) == 0 for c in cl) else 0)
        if all(harm) and voices >= 2:
            return (HARM_ALL, 0)  # harm confirmed by two or more; saturated
        if all(harm):
            return (DISPUTED, 0)  # a lone alarm: one voice, nobody vouching
        level = SAFE_ALL if not any(harm) else DISPUTED
        return (level, -min(c.value for c in cl))

    # ---------------------------------------------------------- acting
    def _propose(self, slot: int, turn_i: int, greedy: bool = False) -> int:
        a0 = Agent._propose(self, slot, turn_i, greedy=greedy)
        ref = self._cur_ref
        if not self.listen or ref is None:
            return a0
        claims = self._credible_claims(ref)
        if not claims:
            return a0
        row = self.q.row(slot)
        if not self.q.flat(row) and self.q.is_explore(slot, turn_i, greedy=greedy):
            return a0
        if self.advice_spent.get(ref, 0) >= self.advice_budget:
            return a0
        keys = {a: self._key(a, slot, row, claims) for a in range(self.n_actions)}
        best = min(keys.values())
        if keys[a0] == best and best[0] != DISPUTED:
            return a0
        order = SCEPTIC_ORDER if best[0] == DISPUTED else CALM_ORDER
        a = next(b for b in order if b < self.n_actions and keys[b] == best)
        if a != a0:
            self.advice_spent[ref] = self.advice_spent.get(ref, 0) + 1
            self.diversions += 1
        return a

    def _rule(self, obs: bytes, turn_i: int, greedy: bool) -> int:
        """Oracle, written apart from _propose/_key/_credible_claims."""
        n = self.n_actions
        slot = self.cam.get(obs)
        row = self.q.row(slot) if slot >= 0 else [0] * n
        a_q = self.q.select(slot, turn_i, greedy=greedy) if slot >= 0 else ACTION_APPROACH
        ref = referent(obs)
        if not self.listen:
            return a_q
        said: Dict[int, List[Tuple[int, int]]] = {}  # action -> [(immediate, value)]
        for a, speakers in self.testimony.by_ref.get(ref, {}).items():
            for sender, (_t, c) in speakers.items():
                d, g = self.disagree.get(sender, 0), self.agree.get(sender, 0)
                if d == 0 or g >= CREDIBLE_RATIO * d:
                    said.setdefault(a, []).append((c.immediate, c.value, sender, g))
        if not said:
            return a_q
        if min(row) != max(row) and self.q.is_explore(slot, turn_i, greedy=greedy):
            return a_q
        if self._rule_spent.get(ref, 0) >= self.advice_budget:
            return a_q
        rank = []
        for a in range(n):
            if slot >= 0 and self.tried.get((slot, a), 0):
                lived = self.lived.get((slot, a), [0, 0])[0]
                rank.append((3 if lived < 0 else 0, -row[a]))
            elif a not in said:
                rank.append((1, -row[a]))
            else:
                bad = sum(1 for x in said[a] if x[0] < 0)
                proven = {x[2] for x in said[a] if x[3] > 0}
                fresh = any(x[3] == 0 for x in said[a])
                if bad == len(said[a]) and len(proven) + int(fresh) >= 2:
                    rank.append((3, 0))
                elif bad == len(said[a]):
                    rank.append((2, 0))
                elif bad == 0:
                    rank.append((0, -min(x[1] for x in said[a])))
                else:
                    rank.append((2, -min(x[1] for x in said[a])))
        top = min(rank)
        if rank[a_q] == top and top[0] != 2:
            return a_q
        for a in ((1, 2, 0) if top[0] == 2 else (0, 1, 2)):
            if a < n and rank[a] == top:
                if a != a_q:
                    self._rule_spent[ref] = self._rule_spent.get(ref, 0) + 1
                return a
        return a_q

    def turn(self, turn_i: int, greedy: bool = False) -> int:
        obs = self.observation(self.env.cell())
        ref = referent(obs)
        before = self.ret
        a = TalkingAgent.turn(self, turn_i, greedy=greedy)  # skip LINK-2's ledger
        r = self.ret - before
        a = int(a) % self.n_actions
        slot = self.cam.get(obs)
        if slot >= 0:
            rec = self.lived.setdefault((slot, a), [0, 0])
            rec[0] += r
            rec[1] += 1
        speakers = self.testimony.by_ref.get(ref, {}).get(a, {})
        fresh = [(s, c) for s, (_t, c) in speakers.items() if (s, ref, a) not in self._verified]
        if not fresh:
            return a
        harmed = r < 0
        said_harm = {s: c.immediate < 0 for s, (_t, c) in speakers.items()}
        disputed = len(set(said_harm.values())) > 1
        for s, c in fresh:
            self._verified.add((s, ref, a))
            if said_harm[s] != harmed:
                self.disagree[s] = self.disagree.get(s, 0) + 1
            elif disputed:
                self.agree[s] = self.agree.get(s, 0) + 1
        return a
