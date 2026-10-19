"""LINK-1 bench. Experiments E0..E6 of docs/LINK1-DESIGN.md.

    python3 -m echo_wsp.link1.bench all --split dev
    python3 -m echo_wsp.link1.bench e4 --split eval
    python3 -m echo_wsp.link1.bench e3          # real speaker -> microphone

Writes lab/link1/<split>/<exp>.json and, for `all`, predictions.json.
Dev seeds 0..15 are for debugging and never count; eval seeds 1000..1063.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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
from echo_wsp.link1.world import LayoutRing

SPLITS = {"dev": tuple(range(0, 16)), "eval": tuple(range(1000, 1064))}
TURNS = 256
ROOT = Path(__file__).resolve().parents[1] / "lab" / "link1"
WORKERS = 8


def _out(split: str, name: str, data) -> Path:
    d = ROOT / split
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return p


# --------------------------------------------------------------- E0, E1
def e0(n: int = 10000, seed: int = 0) -> dict:
    r = random.Random(seed)
    roundtrip_ok = 0
    detected = {1: 0, 2: 0, 3: 0}
    trials = {1: 0, 2: 0, 3: 0}
    for i in range(n):
        f = fr.Frame(act=r.randrange(5), sender=r.randrange(256), seq=r.randrange(256),
                     wsp=bytes(r.randrange(256) for _ in range(16)))
        raw = f.to_bytes()
        if fr.parse(raw) == f and len(raw) == fr.FRAME_BYTES:
            roundtrip_ok += 1
        k = 1 + i % 3
        bad = bytearray(raw)
        for p in r.sample(range(len(bad)), k):
            bad[p] ^= r.randrange(1, 256)
        trials[k] += 1
        if fr.parse(bytes(bad)) is None:
            detected[k] += 1
    return {"frames": n, "roundtrip_ok": roundtrip_ok,
            "corrupted_trials": trials, "corrupted_detected": detected,
            "frame_bytes": fr.FRAME_BYTES, "wsp_bytes": 16}


def _e1_exhaustive(codewords: int, seed: int) -> dict:
    """Every pattern of 1 and 2 wrong symbols, every wrong value."""
    r = random.Random(seed)
    total = ok = 0
    for _ in range(codewords):
        m = [r.randrange(16) for _ in range(rs.K)]
        c = rs.encode(m)
        for i in range(rs.N):
            for vi in range(1, 16):
                cc = list(c)
                cc[i] ^= vi
                total += 1
                ok += rs.decode(cc) == (m, 1)
                for j in range(i + 1, rs.N):
                    for vj in range(1, 16):
                        c2 = list(cc)
                        c2[j] ^= vj
                        total += 1
                        ok += rs.decode(c2) == (m, 2)
    return {"codewords": codewords, "patterns": total, "corrected": ok}


def e1(n: int = 20000, seed: int = 1) -> dict:
    r = random.Random(seed)
    res = {"exhaustive_le2": _e1_exhaustive(3, seed + 1)}
    for ne in range(0, 5):
        ok = fail = wrong = 0
        for _ in range(n // 5):
            m = [r.randrange(16) for _ in range(rs.K)]
            c = rs.encode(m)
            for p in r.sample(range(rs.N), ne):
                c[p] ^= r.randrange(1, 16)
            d, _k = rs.decode(c)
            if d is None:
                fail += 1
            elif d == m:
                ok += 1
            else:
                wrong += 1
        res[str(ne)] = {"blocks": n // 5, "corrected": ok, "failed": fail,
                        "miscorrected": wrong}
    return res


# ------------------------------------------------------------------- E2
def _e2_frame(r: random.Random, i: int, content: str) -> fr.Frame:
    if content == "claim":
        # what agents actually send: a structured CLAIM postcard
        c = Claim(ref=r.randrange(1 << 16), action=r.randrange(3),
                  value=r.randrange(-16, 17), support=10 * r.randrange(1, 11),
                  sender=1)
        return claim_frame(c, i & 0xFF)
    return fr.Frame(act=1, sender=7, seq=i & 0xFF,
                    wsp=bytes(r.randrange(256) for _ in range(16)))


def _e2_point(args) -> dict:
    k_tones, rm, snr, n, base, content = args
    r = random.Random(base)
    ok = lost = bad = fixed = 0
    for i in range(n):
        f = _e2_frame(r, i, content)
        x = modem.modulate(f.to_bytes(), k_tones)
        if rm == "clean":
            y = [0] * r.randrange(0, 8001) + x + [0] * 2000
        else:
            y = room.simulate(x, snr_db=snr, room=rm, seed=base * 1000 + i)
        heard = [h for h in modem.demodulate(y, k_tones) if h.frame is not None]
        if not heard:
            lost += 1
        elif heard[0].frame == f and len(heard) == 1:
            ok += 1
            fixed += heard[0].corrected
        else:
            bad += 1
    return {"K": k_tones, "room": rm, "snr_db": snr, "content": content,
            "frames": n, "ok": ok,
            "lost": lost, "corrupt_accepted": bad, "rs_symbols_fixed": fixed}


def _e2_false(args) -> dict:
    seconds, base = args
    r = random.Random(base)
    x = [0] * (seconds * modem.RATE)
    y = room.simulate(x, snr_db=0.0, room="dry", seed=base, whistle=False)
    # silence in, so add explicit noise and whistles of our own
    y = [max(-32768, min(32767, v + int(r.gauss(0, 3000)))) for v in y]
    y2 = room.simulate([int(r.gauss(0, 3000)) for _ in range(seconds * modem.RATE)],
                       snr_db=30.0, room="echo", seed=base + 1, whistle=True)
    acc = 0
    for buf in (y, y2):
        for k in (1, 2):
            acc += sum(1 for h in modem.demodulate(buf, k) if h.frame is not None)
    return {"seconds": 2 * seconds, "accepted": acc}


def _e2_drift(args) -> dict:
    ppm, n, b = args
    r = random.Random(b)
    ok = lost = bad = 0
    for i in range(n):
        f = fr.Frame(1, 7, i & 0xFF, bytes(r.randrange(256) for _ in range(16)))
        y = room.simulate(modem.modulate(f.to_bytes(), 1), snr_db=10, room="echo",
                          seed=b * 1000 + i, ppm=ppm)
        h = [hh for hh in modem.demodulate(y, 1) if hh.frame is not None]
        if not h:
            lost += 1
        elif h[0].frame == f:
            ok += 1
        else:
            bad += 1
    return {"ppm": ppm, "frames": n, "ok": ok, "lost": lost, "corrupt_accepted": bad}


def e2(split: str) -> dict:
    n = 50 if split == "eval" else 10
    base = 500000 if split == "eval" else 1000
    pts = []
    for content in ("random", "claim"):
        cb = base + (0 if content == "random" else 300000)
        for k in (1, 2):
            pts.append((k, "clean", None, 200 if split == "eval" else 20, cb + k, content))
            for rm in ("dry", "echo"):
                for snr in (30, 20, 10, 5, 0, -5):
                    pts.append((k, rm, snr, n,
                                cb + 100 * k + snr + (50 if rm == "echo" else 0), content))
    drift = [(ppm, n // 2, base + 7000 + ppm) for ppm in (-200, 200)]
    with ProcessPoolExecutor(WORKERS) as ex:
        res = list(ex.map(_e2_point, pts))
        false = list(ex.map(_e2_false, [(30, base + 9000 + i) for i in range(2)]))
        drift_res = list(ex.map(_e2_drift, drift))
    return {"points": res, "noise_only": false, "clock_drift": drift_res,
            "airtime_ms": {"K1": modem.airtime_ms(1), "K2": modem.airtime_ms(2)},
            "payload_bits_per_s": {"K1": 16 * 8 * 1000 // modem.airtime_ms(1),
                                   "K2": 16 * 8 * 1000 // modem.airtime_ms(2)},
            "table_sha256": modem.TABLE_SHA256}


# ------------------------------------------------------------------- E4
def _fresh(env: LayoutRing) -> LayoutRing:
    return LayoutRing(env.seed, kind=list(env._layout))


def _novice(seed: int, frames: Sequence[fr.Frame], env=None, keep=None) -> dict:
    b = TalkingAgent(2, env=env if env is not None else LayoutRing(seed), audit=True)
    before = core_digest(b)
    deliver(b, frames)
    hear_touched = int(core_digest(b) != before)
    b.run(TURNS)
    rep = b.report()
    rep["hear_touched_core"] = hear_touched
    rep["replay_mismatch"] = int(not replay_matches(b, _fresh(b.env)))
    rep["testimony_refs"] = len(b.testimony.by_ref)
    rep["core_sha256"] = core_digest(b)
    if keep is not None:
        keep.append(b)
    return rep


def _shuffle(claims: List[Claim], seed: int) -> List[Claim]:
    refs = sorted({c.ref for c in claims})
    perm = list(refs)
    r = random.Random(seed * 31 + 5)
    if len(refs) > 1:
        while any(a == b for a, b in zip(refs, perm)):
            r.shuffle(perm)
    mp = dict(zip(refs, perm))
    return [Claim(mp[c.ref], c.action, c.value, c.support, c.sender) for c in claims]


def _liar(claims: List[Claim]) -> List[Claim]:
    return [Claim(c.ref, c.action, -c.value, c.support, c.sender) for c in claims]


def over_air(frames: Sequence[fr.Frame], snr: float, seed: int,
             rm: str = "echo") -> Tuple[List[fr.Frame], dict]:
    x = modem.transmit(frames, 1)
    y = room.simulate(x, snr_db=snr, room=rm, seed=seed)
    heard = [h.frame for h in modem.demodulate(y, 1, max_frames=len(frames) + 8)
             if h.frame is not None]
    sent = {f.to_bytes() for f in frames}
    corrupt = sum(1 for f in heard if f.to_bytes() not in sent)
    got = len({f.to_bytes() for f in heard} & sent)
    return heard, {"sent": len(frames), "decoded": got,
                   "lost": len(frames) - got, "corrupt_accepted": corrupt,
                   "airtime_s": len(x) // modem.RATE}


def _dialogue(seed: int, a: TalkingAgent) -> dict:
    b = TalkingAgent(2, env=LayoutRing(seed), audit=True)
    b.env.reset()
    b.q.reset_traces()
    b.clear_context()
    asks = answers = touched = 0
    for t in range(TURNS):
        q = b.question_here()
        if q is not None:
            asks += 1
            replies = a.hear(q) or []
            answers += len(replies)
            before = core_digest(b)
            deliver(b, replies)
            touched += int(core_digest(b) != before)
        b.turn(t)
    rep = b.report()
    rep.update({"asks": asks, "answers": answers, "frames": asks + answers,
                "hear_touched_core": touched,
                "replay_mismatch": int(not replay_matches(b, _fresh(b.env))),
                "testimony_refs": len(b.testimony.by_ref),
                "core_sha256": core_digest(b)})
    return rep


def e4_world(seed: int) -> dict:
    a = TalkingAgent(1, env=LayoutRing(seed))
    a.run(TURNS)
    claims = a.claims()
    frames = [claim_frame(c, i) for i, c in enumerate(claims)]
    out = {"seed": seed, "claims": len(claims),
           "veteran": {k: v for k, v in a.report().items()
                       if k in ("harm", "first_harm", "return")}}
    out["S"] = _novice(seed, [])
    out["T"] = _novice(seed, frames)
    for snr in (10, 0):
        heard, st = over_air(frames, snr, seed * 10 + snr)
        rep = _novice(seed, heard)
        rep["air"] = st
        out[f"A{snr}"] = rep
    xs = _shuffle(claims, seed)
    out["X"] = _novice(seed, [claim_frame(c, i) for i, c in enumerate(xs)])
    ls = _liar(claims)
    out["L"] = _novice(seed, [claim_frame(c, i) for i, c in enumerate(ls)])
    moved = LayoutRing(seed).moved(seed)
    out["D"] = _novice(seed, frames, env=moved)
    out["D_silence"] = _novice(seed, [], env=LayoutRing(seed).moved(seed))
    a2 = TalkingAgent(1, env=LayoutRing(seed))
    a2.run(TURNS)
    out["E5"] = _dialogue(seed, a2)
    return out


def e4(split: str) -> dict:
    seeds = SPLITS[split]
    with ProcessPoolExecutor(WORKERS) as ex:
        worlds = list(ex.map(e4_world, seeds))
    return {"split": split, "turns": TURNS, "advice_budget": ADVICE_BUDGET,
            "worlds": worlds}


# ------------------------------------------------------------------- E6
def e6(split: str, n: int = 16) -> dict:
    """Two real processes, bytes only. Must match the in-process arms."""
    seeds = SPLITS[split][:n]
    env = dict(os.environ)
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    rows = []
    for seed in seeds:
        p = subprocess.run([sys.executable, "-m", "echo_wsp.link1.peer", "speak",
                            "--seed", str(seed)], capture_output=True, env=env,
                           cwd=root, check=True)
        raw = p.stdout
        frames = [fr.parse(raw[i:i + fr.FRAME_BYTES])
                  for i in range(0, len(raw), fr.FRAME_BYTES)]
        bad = sum(1 for f in frames if f is None)
        pipe_T = _novice(seed, [f for f in frames if f is not None])
        a = TalkingAgent(1, env=LayoutRing(seed))
        a.run(TURNS)
        local_T = _novice(seed, [claim_frame(c, i) for i, c in enumerate(a.claims())])
        # dialogue over a pipe
        srv = subprocess.Popen([sys.executable, "-m", "echo_wsp.link1.peer", "serve",
                                "--seed", str(seed)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, env=env, cwd=root)
        b = TalkingAgent(2, env=LayoutRing(seed), audit=True)
        b.env.reset()
        b.q.reset_traces()
        b.clear_context()
        asks = answers = 0
        for t in range(TURNS):
            q = b.question_here()
            if q is not None:
                asks += 1
                srv.stdin.write(q.to_bytes())
                srv.stdin.flush()
                cnt = srv.stdout.read(1)[0]
                for _ in range(cnt):
                    f = fr.parse(srv.stdout.read(fr.FRAME_BYTES))
                    if f is not None:
                        answers += 1
                        deliver(b, [f])
            b.turn(t)
        srv.stdin.write(fr.Frame(fr.ACT_BYE, 2, 0, bytes(16)).to_bytes())
        srv.stdin.close()
        srv.wait(timeout=30)
        pipe_E5 = b.report()
        a2 = TalkingAgent(1, env=LayoutRing(seed))
        a2.run(TURNS)
        local_E5 = _dialogue(seed, a2)
        pipe_E5["core_sha256"] = core_digest(b)
        same = lambda p, q: all(p[k] == q[k] for k in p if k in q
                                and k not in ("asks", "answers", "frames"))
        rows.append({
            "seed": seed, "pipe_bytes": len(raw), "bad_frames": bad,
            "broadcast_identical": pipe_T == local_T,
            "dialogue_identical": same(pipe_E5, local_E5)
            and pipe_E5["core_sha256"] == local_E5["core_sha256"],
            "dialogue_asks": asks, "dialogue_answers": answers,
        })
    return {"split": split, "worlds": rows}


# ------------------------------------------------------------------- E3
def e3(frames_per_level: int = 20, levels=(0.25, 0.5), agents: int = 3) -> dict:
    """Real air on this PC. Plays sound. Mixer state is restored after."""
    from echo_wsp.link1 import audio_io

    if not audio_io.available():
        return {"available": False}
    state = audio_io.mixer_state()
    r = random.Random(77)
    out = {"available": True, "mixer_before": state, "levels": [], "agents": []}
    try:
        sink = audio_io.default_sink()
        # digital loop through PipeWire's monitor: no air
        frames = [fr.Frame(1, 7, i, bytes(r.randrange(256) for _ in range(16)))
                  for i in range(frames_per_level)]
        y = audio_io.play_and_record([0] * 1600 + modem.transmit(frames, 1),
                                     target=sink, capture_sink=True, volume=0.5)
        out["monitor"] = _score_rx(frames, y)
        audio_io.set_mixer({"@DEFAULT_AUDIO_SINK@": ("0.5", False),
                            "@DEFAULT_AUDIO_SOURCE@": ("1.0", False)})
        for vol in levels:
            frames = [fr.Frame(1, 7, i, bytes(r.randrange(256) for _ in range(16)))
                      for i in range(frames_per_level)]
            y = audio_io.play_and_record([0] * 1600 + modem.transmit(frames, 1),
                                         volume=vol)
            rec = _score_rx(frames, y)
            rec["volume"] = vol
            out["levels"].append(rec)
        # agents by air: the veteran's claims go out of the speaker, the
        # novice's world is driven only by what the microphone decoded.
        for seed in SPLITS["dev"][:agents]:
            a = TalkingAgent(1, env=LayoutRing(seed))
            a.run(TURNS)
            frames = a.broadcast()
            y = audio_io.play_and_record([0] * 1600 + modem.transmit(frames, 1),
                                         volume=levels[-1])
            heard = [h.frame for h in modem.demodulate(y, 1, max_frames=len(frames) + 8)
                     if h.frame is not None]
            sent = {f.to_bytes() for f in frames}
            rep = _novice(seed, heard)
            silent = _novice(seed, [])
            wire = _novice(seed, frames)
            out["agents"].append({
                "seed": seed, "sent": len(frames),
                "decoded": len({f.to_bytes() for f in heard} & sent),
                "corrupt_accepted": sum(1 for f in heard if f.to_bytes() not in sent),
                "first_harm_air": rep["first_harm"],
                "first_harm_wire": wire["first_harm"],
                "first_harm_silence": silent["first_harm"],
                "airtime_s": len(frames) * modem.airtime_ms(1) // 1000,
            })
    finally:
        audio_io.set_mixer(state)
        out["mixer_after"] = audio_io.mixer_state()
    return out


def _score_rx(frames: Sequence[fr.Frame], y: Sequence[int]) -> dict:
    hs = modem.demodulate(y, 1, max_frames=len(frames) + 8)
    sent = {f.to_bytes(): f for f in frames}
    good = {h.frame.to_bytes() for h in hs if h.frame is not None} & set(sent)
    corrupt = sum(1 for h in hs if h.frame is not None and h.frame.to_bytes() not in sent)
    peak = max((abs(v) for v in y), default=0)
    return {"frames": len(frames), "decoded": len(good), "lost": len(frames) - len(good),
            "corrupt_accepted": corrupt, "peak": peak,
            "rs_symbols_fixed": sum(h.corrected for h in hs if h.frame is not None)}


# ------------------------------------------------------------ predictions
def _frac(n: int, d: int) -> str:
    return f"{n}/{d}"


def predictions(e2r: dict, e4r: dict) -> dict:
    W = e4r["worlds"]
    n = len(W)
    fh = lambda w, arm: w[arm]["first_harm"]
    p1_win = sum(1 for w in W if fh(w, "T") < fh(w, "S"))
    p1_loss = sum(1 for w in W if fh(w, "T") > fh(w, "S"))
    p2_win = sum(1 for w in W if fh(w, "T") < fh(w, "X"))
    arms = ("S", "T", "A10", "A0", "X", "L", "D", "D_silence", "E5")
    viol = []
    for w in W:
        for arm in arms:
            r = w[arm]
            for k in ("false_facts", "destroyed", "cortex_calls", "foreign_q_writes",
                      "foreign_t_writes", "foreign_cam_allocs", "unexplained_diversions",
                      "hear_touched_core", "replay_mismatch"):
                if r.get(k, 0) != 0:
                    viol.append((w["seed"], arm, k, r[k]))
    p4_bad = [w["seed"] for w in W
              if w["L"]["diversions"] > ADVICE_BUDGET * w["L"]["testimony_refs"]]
    sent = sum(w["A10"]["air"]["sent"] for w in W)
    lost = sum(w["A10"]["air"]["lost"] for w in W)
    corrupt = sum(w[a]["air"]["corrupt_accepted"] for w in W for a in ("A10", "A0"))
    p5_ok = sum(1 for w in W if fh(w, "A10") <= fh(w, "T") + 1)
    p7_frames_e5 = sum(w["E5"]["frames"] for w in W)
    p7_frames_t = sum(w["claims"] for w in W)
    p7_ok = sum(1 for w in W if fh(w, "E5") <= fh(w, "T") + 1)
    pts = {(p["K"], p["room"], p["snr_db"], p["content"]): p for p in e2r["points"]}
    contents = ("random", "claim")
    clean_lost = sum(pts[(k, "clean", None, c)]["lost"]
                     + pts[(k, "clean", None, c)]["corrupt_accepted"]
                     for k in (1, 2) for c in contents)
    echo_hi = [pts[(1, "echo", s, c)] for s in (30, 20, 10) for c in contents]
    echo_per = (sum(p["lost"] + p["corrupt_accepted"] for p in echo_hi),
                sum(p["frames"] for p in echo_hi))
    e2_corrupt = (sum(p["corrupt_accepted"] for p in e2r["points"])
                  + sum(d["corrupt_accepted"] for d in e2r["clock_drift"])
                  + sum(f["accepted"] for f in e2r["noise_only"]))
    res = {
        "P1": {"T_beats_S": _frac(p1_win, n), "T_loses_S": _frac(p1_loss, n),
               "green": p1_win * 4 >= 3 * n and p1_loss * 20 <= n},
        "P2": {"T_beats_X": _frac(p2_win, n), "green": p2_win * 4 >= 3 * n},
        "P3": {"violations": viol, "green": not viol},
        # Holds by construction (advice_spent caps each referent); reported
        # as a code assertion, not a prediction — see the review notes.
        "P4": {"kind": "assertion", "worlds_over_budget": p4_bad, "green": not p4_bad},
        "P5": {"A10_lost": _frac(lost, sent), "corrupt_accepted": corrupt,
               "A10_within_1_of_T": _frac(p5_ok, n),
               "green": lost * 20 <= sent and corrupt == 0 and p5_ok * 10 >= 9 * n},
        "P6": {"clean_lost_or_bad": clean_lost, "echo_snr_ge10_K1": _frac(*echo_per),
               "corrupt_accepted_all_E2": e2_corrupt,
               "green": clean_lost == 0 and echo_per[0] * 100 <= echo_per[1]
               and e2_corrupt == 0},
        "P7": {"frames_E5": p7_frames_e5, "frames_T": p7_frames_t,
               "E5_within_1_of_T": _frac(p7_ok, n),
               "green": p7_frames_e5 < p7_frames_t and p7_ok * 10 >= 9 * n},
    }
    return res


def summary(e4r: dict) -> dict:
    W = e4r["worlds"]
    arms = ("S", "T", "A10", "A0", "X", "L", "D", "D_silence", "E5")
    out = {}
    for arm in arms:
        vals = sorted(w[arm]["first_harm"] for w in W)
        harm = sorted(w[arm]["harm"] for w in W)
        ret = sorted(w[arm]["return"] for w in W)
        out[arm] = {"first_harm_total": sum(vals), "first_harm_median": vals[len(vals) // 2],
                    "harm_median": harm[len(harm) // 2], "return_median": ret[len(ret) // 2],
                    "diversions_total": sum(w[arm]["diversions"] for w in W)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=("e0", "e1", "e2", "e3", "e4", "e6", "all"))
    ap.add_argument("--split", choices=tuple(SPLITS), default="dev")
    args = ap.parse_args(argv)
    t0 = time.time()
    done = {}
    todo = ("e0", "e1", "e2", "e4", "e6") if args.exp == "all" else (args.exp,)
    for name in todo:
        t = time.time()
        if name == "e0":
            r = e0()
        elif name == "e1":
            r = e1()
        elif name == "e2":
            r = e2(args.split)
        elif name == "e3":
            r = e3()
        elif name == "e4":
            r = e4(args.split)
            r["summary"] = summary(r)
        else:
            r = e6(args.split)
        r["seconds"] = round(time.time() - t, 1)
        done[name] = r
        p = _out(args.split if name != "e3" else "air", name, r)
        print(f"{name}: {p} ({r['seconds']} s)", flush=True)
    if args.exp == "all":
        pr = predictions(done["e2"], done["e4"])
        _out(args.split, "predictions", pr)
        for k, v in pr.items():
            print(k, "GREEN" if v["green"] else "RED", {a: b for a, b in v.items() if a != "green"})
        print("summary", json.dumps(done["e4"]["summary"], indent=1))
    print(f"total {round(time.time() - t0, 1)} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
