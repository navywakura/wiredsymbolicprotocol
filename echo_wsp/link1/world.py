"""NEXUS-0's ring with the furniture moved by a seed.

Same 32 cells, same JUMP cells, same rewards and the same physics: this
only overrides where `reset` puts 2 THREAT, 3 GOAL and 1 NOVEL. It also
keeps a running sum of rewards, because `Agent.turn` returns the action
and not what the world paid for it.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from echo_wsp.nexus0.constants import JUMP_CELLS, N_CELLS
from echo_wsp.nexus0.env import (
    KIND_EMPTY,
    KIND_GOAL,
    KIND_NOVEL,
    KIND_THREAT,
    Cell,
    RingEnv,
)


def layout(seed: int) -> List[int]:
    rng = random.Random(int(seed) * 7919 + 17)
    free = [c for c in range(N_CELLS) if c != 0 and c not in JUMP_CELLS]
    picks = rng.sample(free, 6)
    kind = [KIND_EMPTY] * N_CELLS
    for c in picks[:2]:
        kind[c] = KIND_THREAT
    for c in picks[2:5]:
        kind[c] = KIND_GOAL
    kind[picks[5]] = KIND_NOVEL
    return kind


class LayoutRing(RingEnv):
    def __init__(self, seed: int, kind: Optional[List[int]] = None) -> None:
        self._layout = list(kind) if kind is not None else layout(seed)
        if len(self._layout) != N_CELLS:
            raise ValueError("a ring has 32 cells")
        self.ret = 0
        self.harm = 0
        super().__init__(seed=seed)

    def reset(self) -> None:
        super().reset()
        self.kind = list(self._layout)
        self.ret = 0
        self.harm = 0

    def step(self, a: int) -> Tuple[int, Cell]:
        r, c = super().step(a)
        self.ret += int(r)
        if r < 0:
            self.harm += 1
        return r, c

    def moved(self, seed: int) -> "LayoutRing":
        """The same world after its two threats moved to other empty cells."""
        rng = random.Random(int(seed) * 104729 + 3)
        kind = list(self._layout)
        old = [i for i, k in enumerate(kind) if k == KIND_THREAT]
        free = [c for c in range(N_CELLS) if kind[c] == KIND_EMPTY
                and c != 0 and c not in JUMP_CELLS]
        new = rng.sample(free, len(old))
        for c in old:
            kind[c] = KIND_EMPTY
        for c in new:
            kind[c] = KIND_THREAT
        return LayoutRing(self.seed, kind=kind)
