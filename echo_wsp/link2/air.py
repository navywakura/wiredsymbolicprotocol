"""LINK-2 F4 (real air, this PC) and F5 (against ggwave).

    python3 -m echo_wsp.link2.air sim  --ggwave-python <venv python>
    python3 -m echo_wsp.link2.air real --ggwave-python <venv python>

`real` plays sound and changes the mixer; the state is saved first and
restored in a finally block. Microphone recordings are kept only as
counts in the JSON, never as audio files.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Sequence

from echo_wsp.link1 import audio_io, room
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev
from echo_wsp.link2 import phy
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.bench import HONEST, SESSION, TRIBE

ROOT = Path(__file__).resolve().parents[1] / "lab" / "link2" / "air"
RUNNER = Path(__file__).resolve().parent / "ggwave_runner.py"
SINK = "@DEFAULT_AUDIO_SINK@"
SOURCE = "@DEFAULT_AUDIO_SOURCE@"


def _frames(seed: int = 3, n: int = 10) -> List[bytes]:
    """n sealed CLAIM2 envelopes from a veteran of a dev world (repeated if short)."""
    a = TalkingAgent2(HONEST, env=LayoutRing(seed))
    a.run(256)
    envs = a.envs()
    out = []
    i = 0
    while len(out) < n:
        e = envs[i % len(envs)]
        out.append(ev.seal(ev.Env(e.act, e.sender, len(out), e.wsp), TRIBE[HONEST], SESSION))
        i += 1
    return out


def _count(raws: Sequence[bytes], y: Sequence[int]) -> dict:
    g = ev.Guard(TRIBE, SESSION)
    sent = set(raws)
    ok = bad = 0
    for h in phy.demodulate(y, max_frames=len(raws) + 8):
        if h.raw is None:
            continue
        e = g.admit(h.raw)
        if e is None:
            continue
        if h.raw in sent:
            ok += 1
        else:
            bad += 1
    peak = max((abs(v) for v in y), default=0)
    clipped = sum(1 for v in y if abs(v) >= 32767)
    return {"frames": len(raws), "decoded": ok, "corrupt_accepted": bad,
            "lost": len(raws) - ok, "peak": peak,
            "clipped_per_mille": 1000 * clipped // max(1, len(y)),
            "refused": dict(sorted(g.refused.items()))}


# One loudness for every cell: the gain that keeps the noisiest cell (0 dB)
# from clipping, applied to all, so a lost frame means noise, not a quieter
# signal (independent review, finding 5).
K_GAIN = 1.0 / (1.0 + 3.0 * math.sqrt(1.0))


def _noisy(x: Sequence[int], snr_db, seed: int) -> List[int]:
    """Mix white noise into the emitted signal (it then leaves the real speaker)."""
    rng = random.Random(seed)
    act = [v for v in x if v]
    ps = sum(v * v for v in act) / max(1, len(act))
    sigma = 0.0 if snr_db is None else math.sqrt(ps / (10 ** (snr_db / 10)))
    return [max(-32768, min(32767, int(K_GAIN * (v + (rng.gauss(0, sigma) if sigma else 0)))))
            for v in x]


def sim(ggwave_python: str) -> dict:
    rng = random.Random(5)
    ours = []
    for snr in (10, 0, -5):
        raws = _frames(n=30)
        ok = bad = 0
        for i, raw in enumerate(raws):
            y = room.simulate(phy.modulate(raw), snr_db=snr, room="echo",
                              seed=7000 + 10 * (snr + 5) + i)
            c = _count([raw], y)
            ok += c["decoded"]
            bad += c["corrupt_accepted"]
        ours.append({"snr_db": snr, "frames": 30, "ok": ok, "corrupt_accepted": bad,
                     "airtime_ms": phy.airtime_ms()})
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "gg.json")
        subprocess.run([ggwave_python, "-I", str(RUNNER), "sim", out], check=True)
        gg = json.load(open(out))
    del rng
    return {"ours_K1_v2": ours, "ggwave": gg,
            "note": "same 27-byte payload; echo room taps scaled to each sample rate"}


def _set(sink_vol: str, src_vol: str) -> None:
    audio_io.set_mixer({SINK: (sink_vol, False), SOURCE: (src_vol, False)})


def real(ggwave_python: str, per_cell: int = 10) -> dict:
    if not audio_io.available():
        return {"available": False}
    state = audio_io.mixer_state()
    res = {"mixer_before": state, "grid": [], "ggwave": [], "airplay": None}
    try:
        for src in ("0.3", "0.6", "1.0"):
            for snr in (None, 10, 0):
                raws = _frames(n=per_cell)
                x = [0] * 1600 + phy.transmit(raws)
                _set("0.5", src)
                y = audio_io.play_and_record(_noisy(x, snr, 11), volume=0.35)
                c = _count(raws, y)
                c.update({"mic_volume": src, "added_noise_snr_db": snr})
                res["grid"].append(c)
                print("grid", c, flush=True)
        # ggwave over the same air, mic 0.6, no added noise
        _set("0.5", "0.6")
        with tempfile.TemporaryDirectory() as d:
            for proto in (0, 1, 2):
                rng = random.Random(100 + proto)
                ok = 0
                n = per_cell
                for i in range(n):
                    p = bytes(rng.randrange(256) for _ in range(27))
                    tx = os.path.join(d, "gg.wav")
                    subprocess.run([ggwave_python, "-I", str(RUNNER), "tx", p.hex(), str(proto), tx],
                                   check=True)
                    rx = os.path.join(d, "rx.wav")
                    rec = subprocess.Popen(["pw-record", "--rate", "48000", "--channels", "1",
                                            "--format", "s16", rx],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        time.sleep(0.5)
                        subprocess.run(["pw-play", "--volume", "0.35", tx], check=True)
                        time.sleep(0.8)
                    finally:
                        rec.send_signal(2)
                        try:
                            rec.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            rec.kill()
                    js = os.path.join(d, "rx.json")
                    subprocess.run([ggwave_python, "-I", str(RUNNER), "rx", rx, js], check=True)
                    ok += p.hex() in json.load(open(js))
                res["ggwave"].append({"proto": proto, "frames": n, "ok": ok})
                print("ggwave", res["ggwave"][-1], flush=True)
            # ours at the same setting, for the side-by-side
            raws = _frames(n=per_cell)
            y = audio_io.play_and_record([0] * 1600 + phy.transmit(raws), volume=0.35)
            res["ours_same_setting"] = _count(raws, y)
        # a second device: the AirPlay sink, if it answers
        sinks = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True,
                               text=True).stdout
        raop = [ln.split()[1] for ln in sinks.splitlines() if "raop_sink" in ln]
        if raop:
            raws = _frames(n=3)
            x = [0] * 1600 + phy.transmit(raws)
            with tempfile.TemporaryDirectory() as d:
                tx = os.path.join(d, "tx.wav")
                rx = os.path.join(d, "rx.wav")
                audio_io.write_wav(tx, x)
                rec = subprocess.Popen(["pw-record", "--rate", "16000", "--channels", "1",
                                        "--format", "s16", rx],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    time.sleep(0.5)
                    p = subprocess.run(["timeout", "40", "pw-play", "--target", raop[0],
                                        "--volume", "0.5", tx])
                    time.sleep(4.0)  # AirPlay buffers about two seconds
                finally:
                    rec.send_signal(2)
                    try:
                        rec.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        rec.kill()
                y = audio_io.read_wav(rx)
            c = _count(raws, y)
            c.update({"sink": raop[0], "pw_play_rc": p.returncode})
            res["airplay"] = c
            print("airplay", c, flush=True)
    finally:
        audio_io.set_mixer(state)
        res["mixer_after"] = audio_io.mixer_state()
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("sim", "real"))
    ap.add_argument("--ggwave-python", required=True)
    args = ap.parse_args(argv)
    ROOT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    r = sim(args.ggwave_python) if args.mode == "sim" else real(args.ggwave_python)
    r["seconds"] = round(time.time() - t0, 1)
    p = ROOT / f"{args.mode}.json"
    p.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
    print(p, json.dumps(r)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
