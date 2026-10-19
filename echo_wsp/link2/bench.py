"""LINK-2 bench. Experiments F0..F3 of docs/LINK2-DESIGN.md (F4/F5: air.py).

    python3 -m echo_wsp.link2.bench all --split dev
    python3 -m echo_wsp.link2.bench all --split eval

Writes lab/link2/<split>/<exp>.json and predictions.json.
Dev seeds 0..15 never count; eval seeds 2000..2063.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Sequence

from echo_wsp.link1.agent import core_digest, replay_matches
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.speech2 import Claim2, env as claim_env

SPLITS = {"dev": tuple(range(0, 16)), "eval": tuple(range(2000, 2064))}
REGRESSION = (1012, 1055)  # LINK-1's two failures, reported, never predicted
TURNS = 256
ROOT = Path(__file__).resolve().parents[1] / "lab" / "link2"
WORKERS = 8

HONEST, LIAR, LIAR2, NOVICE = 1, 3, 4, 2
TRIBE = {s: ev.test_key(f"agent-{s}") for s in (HONEST, LIAR, LIAR2, NOVICE)}
SESSION = ev.test_session("world-session")
OTHER_SESSION = ev.test_session("an-older-session")


def _out(split: str, name: str, data) -> Path:
    d = ROOT / split
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return p


# ------------------------------------------------------------------- F0
def f0(n_forged: int = 100000, seed: int = 0) -> dict:
    r = random.Random(seed)
    res: Dict[str, int] = {}
    good = [ev.Env(5, HONEST, i, bytes(r.randrange(256) for _ in range(16))) for i in range(2000)]
    sealed = [ev.seal(e, TRIBE[HONEST], SESSION) for e in good]
    g = ev.Guard(TRIBE, SESSION)
    res["roundtrip_ok"] = sum(1 for e, raw in zip(good, sealed) if g.admit(raw) == e)
    # forged: valid shape and CRC, random tag, claiming to be a tribe member
    g = ev.Guard(TRIBE, SESSION)
    acc = 0
    for i in range(n_forged):
        body = bytes([ev.MAGIC, (ev.VERSION << 4) | 5, HONEST]) + (i & 0xFFFF).to_bytes(2, "big")
        body += bytes(r.randrange(256) for _ in range(16)) + bytes(r.randrange(256) for _ in range(4))
        raw = body + ev.crc16(body).to_bytes(2, "big")
        acc += g.admit(raw) is not None
    res["forged_frames"] = n_forged
    res["forged_accepted"] = acc
    # a stranger with its own key, spoofing the honest sender id
    g = ev.Guard(TRIBE, SESSION)
    stranger = ev.test_key("stranger")
    res["spoofed_accepted"] = sum(
        1 for i in range(1000)
        if g.admit(ev.seal(ev.Env(5, HONEST, i, bytes(16)), stranger, SESSION)) is not None)
    # replay from another session, and replay inside the same session
    g = ev.Guard(TRIBE, SESSION)
    old = [ev.seal(e, TRIBE[HONEST], OTHER_SESSION) for e in good[:500]]
    res["other_session_accepted"] = sum(1 for raw in old if g.admit(raw) is not None)
    g = ev.Guard(TRIBE, SESSION)
    first = sum(1 for raw in sealed[:500] if g.admit(raw) is not None)
    again = sum(1 for raw in sealed[:500] if g.admit(raw) is not None)
    res["same_session_first"] = first
    res["same_session_replay_accepted"] = again
    # one flipped bit anywhere after sealing
    g = ev.Guard(TRIBE, SESSION)
    flips = 0
    for i, raw in enumerate(sealed[500:1500]):
        b = bytearray(raw)
        b[r.randrange(ev.ENV_BYTES)] ^= 1 << r.randrange(8)
        flips += g.admit(bytes(b)) is not None
    res["bitflip_accepted"] = flips
    res["refused_reasons_last_guard"] = g.refused
    # tampering that recomputes the CRC: only the MAC can stop it
    g = ev.Guard(TRIBE, SESSION)
    tam = 0
    for i, raw in enumerate(sealed[1500:2000]):
        b = bytearray(raw)
        j = (3, 4, 5 + r.randrange(16), 2, 21 + r.randrange(4))[i % 5]  # seq, postcard, sender, tag
        b[j] ^= 1 << r.randrange(8)
        b[25:27] = ev.crc16(bytes(b[:25])).to_bytes(2, "big")
        tam += g.admit(bytes(b)) is not None
    res["tamper_with_crc_accepted"] = tam
    res["tamper_refused_reasons"] = g.refused
    return res


# ------------------------------------------------------------- novices
def _liar(cl: List[Claim2], sender: int) -> List[Claim2]:
    return [Claim2(c.ref, c.action, -c.value, -c.immediate, c.support, sender) for c in cl]


def _as(cl: List[Claim2], sender: int) -> List[Claim2]:
    return [Claim2(c.ref, c.action, c.value, c.immediate, c.support, sender) for c in cl]


def _strategic(cl: List[Claim2], sender: int) -> List[Claim2]:
    """Truth everywhere, plus: at every place where some action hurts, every
    other action 'pays -100 now and later' (reviewer's attack)."""
    bad = {(c.ref, c.action) for c in cl if c.immediate < 0}
    refs = {r for r, _a in bad}
    lies = [Claim2(r, a, -100, -100, 100, sender)
            for r in sorted(refs) for a in range(3) if (r, a) not in bad]
    lied = {(c.ref, c.action) for c in lies}
    truth = [Claim2(c.ref, c.action, c.value, c.immediate, c.support, sender)
             for c in cl if (c.ref, c.action) not in lied]
    return truth + lies


def _v_only_liar(cl: List[Claim2], sender: int) -> List[Claim2]:
    """Flips the value only where the immediate reward is 0 (never caught)."""
    return [Claim2(c.ref, c.action, -c.value if c.immediate == 0 else c.value,
                   c.immediate, c.support, sender) for c in cl]


def _novice(seed: int, raws: Sequence[bytes], *, trust: bool, env=None,
            learn: bool = True, tie: str = "cautious") -> dict:
    b = TalkingAgent2(NOVICE, env=env if env is not None else LayoutRing(seed),
                      trust=trust, learn=learn, tie=tie, audit=True)
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
    rep["replay_mismatch"] = int(not replay_matches(
        b, LayoutRing(b.env.seed, kind=list(b.env._layout))))
    rep["refused"] = dict(sorted(g.refused.items()))
    return rep


def _seal_all(cl: List[Claim2], key: bytes, session: bytes = SESSION, start: int = 0) -> List[bytes]:
    return [ev.seal(claim_env(c, start + i), key, session) for i, c in enumerate(cl)]


def world(seed: int) -> dict:
    a = TalkingAgent2(HONEST, env=LayoutRing(seed))
    a.run(TURNS)
    cl = a.claims2()
    honest = _seal_all(cl, TRIBE[HONEST])
    value_only = _seal_all([Claim2(c.ref, c.action, c.value, 0, c.support, c.sender)
                            for c in cl if c.value], TRIBE[HONEST])
    out = {"seed": seed, "claims": len(cl)}
    # F1 — consequence (single honest speaker, no trust: LINK-1 semantics)
    out["S"] = _novice(seed, [], trust=False)
    out["T1"] = _novice(seed, value_only, trust=False)
    out["T2"] = _novice(seed, honest, trust=False)
    # F2 — outsiders: a stranger spoofing id 1 without the key, and a
    # recording of a liar from another session (valid key, wrong session)
    stranger = ev.test_key("stranger")
    forged = _seal_all(_liar(cl, HONEST), stranger, start=1000)
    mixed = [x for pair in zip(honest, forged) for x in pair] + forged[len(honest):]
    out["O"] = _novice(seed, mixed, trust=False)
    old = _seal_all(_liar(cl, LIAR), TRIBE[LIAR], OTHER_SESSION)
    out["R"] = _novice(seed, honest + old + honest, trust=False)
    # F3 — insiders with the key
    liar = _seal_all(_liar(cl, LIAR), TRIBE[LIAR])
    liar2 = _seal_all(_liar(cl, LIAR2), TRIBE[LIAR2])
    out["H"] = _novice(seed, honest, trust=True)
    out["HL_naive"] = _novice(seed, honest + liar, trust=False)
    out["HL_trust"] = _novice(seed, honest + liar, trust=True)
    out["HLL_trust"] = _novice(seed, honest + liar + liar2, trust=True)
    # context arms from the independent review — no predictions
    out["HL_frozen"] = _novice(seed, honest + liar, trust=True, learn=False)
    out["HL_optimist"] = _novice(seed, honest + liar, trust=True, tie="optimist")
    out["HLs_trust"] = _novice(seed, honest + _seal_all(_strategic(cl, LIAR), TRIBE[LIAR]),
                               trust=True)
    out["HLv_trust"] = _novice(seed, honest + _seal_all(_v_only_liar(cl, LIAR), TRIBE[LIAR]),
                               trust=True)
    return out


def run(split: str) -> dict:
    seeds = SPLITS[split]
    with ProcessPoolExecutor(WORKERS) as ex:
        worlds = list(ex.map(world, seeds))
        regression = list(ex.map(world, REGRESSION))
    return {"split": split, "turns": TURNS, "worlds": worlds,
            "regression_link1_failures": [
                {"seed": w["seed"], **{a: w[a]["first_harm"] for a in ("S", "T1", "T2")},
                 "return_T1": w["T1"]["return"], "return_T2": w["T2"]["return"]}
                for w in regression]}


ARMS = ("S", "T1", "T2", "O", "R", "H", "HL_naive", "HL_trust", "HLL_trust",
        "HL_frozen", "HL_optimist", "HLs_trust", "HLv_trust")


def summary(r: dict) -> dict:
    W = r["worlds"]
    out = {}
    for arm in ARMS:
        fh = sorted(w[arm]["first_harm"] for w in W)
        ret = sorted(w[arm]["return"] for w in W)
        out[arm] = {"first_harm_total": sum(fh), "first_harm_median": fh[len(fh) // 2],
                    "return_median": ret[len(ret) // 2],
                    "harm_median": sorted(w[arm]["harm"] for w in W)[len(W) // 2],
                    "liar_distrusted_worlds": sum(1 for w in W if LIAR in w[arm].get("distrusted", []))}
    return out


def predictions(f0r: dict, r: dict) -> dict:
    W = r["worlds"]
    n = len(W)
    fh = lambda w, a: w[a]["first_harm"]
    med = lambda a: sorted(w[a]["return"] for w in W)[n // 2]
    t2_zero = sum(1 for w in W if fh(w, "T2") == 0)
    t1_bad = [w["seed"] for w in W if fh(w, "T1") > 0]
    t2_worse = [w["seed"] for w in W if fh(w, "T2") > fh(w, "T1")]
    q3_world = sum(1 for w in W if fh(w, "O") == fh(w, "T2") and fh(w, "R") == fh(w, "T2"))
    q4a = sum(1 for w in W if fh(w, "HL_trust") < fh(w, "HL_naive"))
    q4b = sum(1 for w in W if fh(w, "HL_trust") <= fh(w, "H") + 1)
    q5 = sum(1 for w in W if fh(w, "HLL_trust") <= fh(w, "S"))
    viol = []
    for w in W:
        for a in ARMS:
            x = w[a]
            for k in ("false_facts", "destroyed", "cortex_calls", "unexplained_diversions",
                      "hear_touched_core", "replay_mismatch", "foreign_q_writes",
                      "foreign_t_writes", "foreign_cam_allocs"):
                if x.get(k, 0):
                    viol.append((w["seed"], a, k, x[k]))
    return {
        "Q1": {"T2_zero": f"{t2_zero}/{n}", "sum_T1": sum(fh(w, "T1") for w in W),
               "sum_T2": sum(fh(w, "T2") for w in W), "worlds_T1_paid": t1_bad,
               "worlds_T2_worse_than_T1": t2_worse,
               "green": t2_zero * 64 >= 63 * n and not t2_worse
               and sum(fh(w, "T2") for w in W) <= sum(fh(w, "T1") for w in W)},
        "Q2": {"median_return_T1": med("T1"), "median_return_T2": med("T2"),
               "green": med("T2") >= med("T1") - 16},
        "Q3": {"forged_accepted": f0r["forged_accepted"], "spoofed_accepted": f0r["spoofed_accepted"],
               "replays_accepted": f0r["other_session_accepted"] + f0r["same_session_replay_accepted"],
               "O_and_R_equal_T2": f"{q3_world}/{n}",
               "tamper_with_crc_accepted": f0r["tamper_with_crc_accepted"],
               "green": f0r["forged_accepted"] == 0 and f0r["spoofed_accepted"] == 0
               and f0r["other_session_accepted"] == 0 and f0r["same_session_replay_accepted"] == 0
               and f0r["tamper_with_crc_accepted"] == 0 and q3_world == n},
        "Q4": {"HL_trust_beats_naive": f"{q4a}/{n}", "HL_trust_within_1_of_H": f"{q4b}/{n}",
               "green": q4a * 4 >= 3 * n and q4b * 10 >= 9 * n},
        "Q5": {"HLL_trust_not_worse_than_S": f"{q5}/{n}", "green": q5 * 10 >= 9 * n},
        "Q6": {"violations": viol, "green": not viol},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=("f0", "worlds", "all"))
    ap.add_argument("--split", choices=tuple(SPLITS), default="dev")
    args = ap.parse_args(argv)
    t0 = time.time()
    res = {}
    if args.exp in ("f0", "all"):
        res["f0"] = f0()
        _out(args.split, "f0", res["f0"])
        print("f0", json.dumps(res["f0"]), flush=True)
    if args.exp in ("worlds", "all"):
        r = run(args.split)
        r["summary"] = summary(r)
        res["worlds"] = r
        _out(args.split, "worlds", r)
        print("summary", json.dumps(r["summary"], indent=1), flush=True)
        print("regression", r["regression_link1_failures"], flush=True)
    if args.exp == "all":
        pr = predictions(res["f0"], res["worlds"])
        _out(args.split, "predictions", pr)
        for k, v in pr.items():
            print(k, "GREEN" if v["green"] else "RED", {a: b for a, b in v.items() if a != "green"})
    print(f"total {round(time.time() - t0, 1)} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
