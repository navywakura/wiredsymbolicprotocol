"""LINK-3 bench (docs/LINK3-DESIGN.md).

    python3 -m echo_wsp.link3.bench --split dev
    python3 -m echo_wsp.link3.bench --split eval

Every attacker arm runs twice on the same world: with LINK-2's rule (L2,
TalkingAgent2 with trust) and with LINK-3's (L3). Dev 0..15, eval 3000..3063.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List, Sequence

from echo_wsp.link1.agent import core_digest, replay_matches
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.bench import (
    HONEST, LIAR, LIAR2, NOVICE, SESSION, TRIBE, _liar, _seal_all, _strategic,
)
from echo_wsp.link2.speech2 import Claim2
from echo_wsp.link3.agent3 import TalkingAgent3
from echo_wsp.nexus0.constants import ACTION_APPROACH, ACTION_AVOID

SPLITS = {"dev": tuple(range(0, 16)), "eval": tuple(range(3000, 3064))}
TURNS = 256
ROOT = Path(__file__).resolve().parents[1] / "lab" / "link3"
WORKERS = 8
ATTACKS = ("H", "HL", "HLs", "HLv2", "HLL", "HLLs", "HLn", "HLw")


def selective_inverter(cl: List[Claim2], sender: int) -> List[Claim2]:
    """Strategic liar v2: truth at safe places; at harmful places it swaps
    what is said of approach and avoid (an action the honest did not speak
    about gets the honest's other claim, or the inverted sign)."""
    bad_refs = {c.ref for c in cl if c.immediate < 0}
    by = {(c.ref, c.action): c for c in cl}
    out = []
    for c in cl:
        if c.ref not in bad_refs:
            out.append(Claim2(c.ref, c.action, c.value, c.immediate, c.support, sender))
    for r in sorted(bad_refs):
        for a, other in ((ACTION_APPROACH, ACTION_AVOID), (ACTION_AVOID, ACTION_APPROACH)):
            src = by.get((r, other))
            own = by.get((r, a))
            if src is not None:
                v, i, s = src.value, src.immediate, src.support
            elif own is not None:
                v, i, s = -own.value, -own.immediate, own.support
            else:
                continue
            out.append(Claim2(r, a, v, i, s, sender))
        w = by.get((r, 2))
        if w is not None:
            out.append(Claim2(r, 2, w.value, w.immediate, w.support, sender))
    return out


def sybil_novel(cl: List[Claim2], sender: int) -> List[Claim2]:
    """Reviewer F1: truth, plus 'avoid/wait hurt' (-16, -100) for actions the
    honest never spoke about at places where it raised an alarm."""
    spoke = {(c.ref, c.action) for c in cl}
    alarms = {c.ref for c in cl if c.immediate < 0}
    out = [Claim2(c.ref, c.action, c.value, c.immediate, c.support, sender) for c in cl]
    for r in sorted(alarms):
        for a in (1, 2):
            if (r, a) not in spoke:
                out.append(Claim2(r, a, -100, -16, 100, sender))
    return out


def wait_inflation(cl: List[Claim2], sender: int) -> List[Claim2]:
    """Reviewer F2: truth, plus 'wait is safe and worth +100' everywhere the
    honest spoke (no world knowledge needed)."""
    out = [Claim2(c.ref, c.action, c.value, c.immediate, c.support, sender) for c in cl]
    for r in sorted({c.ref for c in cl}):
        out.append(Claim2(r, 2, 100, 0, 100, sender))
    return out


def _novice(cls, seed: int, raws: Sequence[bytes]) -> dict:
    b = cls(NOVICE, env=LayoutRing(seed), trust=True, audit=True)
    g = ev.Guard(TRIBE, SESSION)
    before = core_digest(b)
    for raw in raws:
        e = g.admit(raw)
        if e is not None:
            b.hear2(e)
    touched = int(core_digest(b) != before)
    b.run(TURNS)
    rep = b.report()
    rep["hear_touched_core"] = touched
    rep["replay_mismatch"] = int(not replay_matches(b, LayoutRing(seed)))
    return rep


def world(seed: int) -> dict:
    a = TalkingAgent2(HONEST, env=LayoutRing(seed))
    a.run(TURNS)
    cl = a.claims2()
    h = _seal_all(cl, TRIBE[HONEST])
    feeds = {
        "H": h,
        "HL": h + _seal_all(_liar(cl, LIAR), TRIBE[LIAR]),
        "HLs": h + _seal_all(_strategic(cl, LIAR), TRIBE[LIAR]),
        "HLv2": h + _seal_all(selective_inverter(cl, LIAR), TRIBE[LIAR]),
        "HLL": h + _seal_all(_liar(cl, LIAR), TRIBE[LIAR]) + _seal_all(_liar(cl, LIAR2), TRIBE[LIAR2]),
        # context arms from the independent review (no predictions)
        "HLLs": h + _seal_all(sybil_novel(cl, LIAR), TRIBE[LIAR]) + _seal_all(sybil_novel(cl, LIAR2), TRIBE[LIAR2]),
        "HLn": h + _seal_all(sybil_novel(cl, LIAR), TRIBE[LIAR]),
        "HLw": h + _seal_all(wait_inflation(cl, LIAR), TRIBE[LIAR]),
    }
    out = {"seed": seed, "claims": len(cl), "S": _novice(TalkingAgent3, seed, [])}
    for arm, raws in feeds.items():
        out["L2_" + arm] = _novice(TalkingAgent2, seed, raws)
        out["L3_" + arm] = _novice(TalkingAgent3, seed, raws)
    return out


def summary(W: list) -> dict:
    arms = ["S"] + [f"{r}_{a}" for a in ATTACKS for r in ("L2", "L3")]
    med = lambda xs: sorted(xs)[len(xs) // 2]
    return {arm: {"first_harm_total": sum(w[arm]["first_harm"] for w in W),
                  "harm_median": med([w[arm]["harm"] for w in W]),
                  "return_median": med([w[arm]["return"] for w in W]),
                  "liar_distrusted_worlds": sum(1 for w in W if LIAR in w[arm].get("distrusted", []))}
            for arm in arms}


def predictions(W: list) -> dict:
    n = len(W)
    fh = lambda w, a: w[a]["first_harm"]
    med = lambda a: sorted(w[a]["harm"] for w in W)[n // 2]
    r1 = sum(1 for w in W if fh(w, "L3_HLs") <= fh(w, "L3_H") + 1)
    s1 = (sum(fh(w, "L3_HLs") for w in W), sum(fh(w, "L2_HLs") for w in W))
    r2 = sum(1 for w in W if fh(w, "L3_HLv2") <= 1)
    s2 = (sum(fh(w, "L3_HLv2") for w in W), sum(fh(w, "L2_HLv2") for w in W))
    r3a = sum(1 for w in W if fh(w, "L3_H") == fh(w, "L2_H"))
    r3b = sum(1 for w in W if fh(w, "L3_HL") <= fh(w, "L3_H") + 1)
    r4 = {a: sum(1 for w in W if fh(w, "L3_" + a) <= fh(w, "S")) for a in ("HL", "HLs", "HLv2", "HLL")}
    viol = []
    for w in W:
        for arm, r in w.items():
            if not isinstance(r, dict):
                continue
            for k in ("false_facts", "destroyed", "cortex_calls", "unexplained_diversions",
                      "hear_touched_core", "replay_mismatch", "foreign_q_writes",
                      "foreign_t_writes", "foreign_cam_allocs"):
                if r.get(k, 0):
                    viol.append((w["seed"], arm, k, r[k]))
    return {
        "R1": {"L3_HLs_within_1_of_H": f"{r1}/{n}", "sum_L3_vs_L2": s1,
               "green": r1 * 10 >= 9 * n and s1[0] < s1[1]},
        "R2": {"L3_HLv2_le_1": f"{r2}/{n}", "sum_L3_vs_L2": s2,
               "green": r2 * 10 >= 9 * n and s2[0] <= s2[1]},
        "R3": {"L3_H_equals_L2_H": f"{r3a}/{n}", "L3_HL_within_1_of_H": f"{r3b}/{n}",
               "green": r3a == n and r3b * 10 >= 9 * n},
        "R4": {"not_worse_than_silence": {a: f"{v}/{n}" for a, v in r4.items()},
               "green": all(v * 10 >= 9 * n for v in r4.values())},
        "R5": {"median_harm_L3_HLs": med("L3_HLs"), "median_harm_S": med("S"),
               "green": med("L3_HLs") <= med("S")},
        "R6": {"violations": viol, "green": not viol},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=tuple(SPLITS), default="dev")
    args = ap.parse_args(argv)
    t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        W = list(ex.map(world, SPLITS[args.split]))
    res = {"split": args.split, "worlds": W, "summary": summary(W)}
    pr = predictions(W)
    d = ROOT / args.split
    d.mkdir(parents=True, exist_ok=True)
    (d / "worlds.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    (d / "predictions.json").write_text(json.dumps(pr, indent=1, sort_keys=True) + "\n")
    for arm, v in res["summary"].items():
        print(f"{arm:10s}", v)
    for k, v in pr.items():
        print(k, "GREEN" if v["green"] else "RED", {a: b for a, b in v.items() if a != "green"})
    print(f"total {round(time.time() - t0, 1)} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
