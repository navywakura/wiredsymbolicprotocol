"""ggwave side of F5. Runs in its own venv (ggwave is not an echoai
dependency), e.g.:

    <venv>/bin/python -I echo_wsp/link2/ggwave_runner.py sim  OUT.json
    <venv>/bin/python -I echo_wsp/link2/ggwave_runner.py tx   PAYLOAD_HEX PROTO OUT.wav
    <venv>/bin/python -I echo_wsp/link2/ggwave_runner.py rx   IN.wav OUT.json

`sim` passes 27-byte payloads through the same room model LINK-2 uses
(echo taps scaled to 48 kHz, white noise at a fixed SNR over the active
signal, random lead) and counts exact recoveries. Self-contained: no
echoai imports, so it can run isolated.
"""

from __future__ import annotations

import json
import math
import random
import struct
import sys
import wave

import ggwave

ECHO_TAPS_16K = ((0, 1.0), (23, 0.6), (71, -0.4), (160, 0.3), (420, 0.2), (900, 0.1))
RATE = 48000


def encode(payload: bytes, proto: int) -> list:
    raw = ggwave.encode(payload, protocolId=proto, volume=50)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def decode(samples: list) -> list:
    inst = ggwave.init()
    out = []
    buf = struct.pack(f"<{len(samples)}f", *samples)
    for i in range(0, len(buf), 4096):
        r = ggwave.decode(inst, buf[i:i + 4096])
        if r:
            out.append(bytes(r))
    ggwave.free(inst)
    return out


def room(x: list, snr_db: float, seed: int) -> list:
    rng = random.Random(seed)
    taps = [(3 * d, g) for d, g in ECHO_TAPS_16K]
    span = max(d for d, _ in taps)
    y = [0.0] * (len(x) + span)
    for d, g in taps:
        for i, v in enumerate(x):
            if v:
                y[i + d] += g * v
    act = [v for v in y if v]
    ps = sum(v * v for v in act) / max(1, len(act))
    # Same noise per hertz as LINK-2's 16 kHz room: white noise at 48 kHz
    # spreads over three times the band, so its power is tripled (review,
    # finding 4). SNR here is therefore the 16 kHz-equivalent SNR.
    sigma = math.sqrt(3.0 * ps / (10 ** (snr_db / 10))) if ps else 0.0
    lead = rng.randrange(0, 24001)
    tot = [0.0] * lead + y + [0.0] * 12000
    return [max(-1.0, min(1.0, v + rng.gauss(0, sigma))) for v in tot]


def main() -> int:
    ggwave.disableLog()
    mode = sys.argv[1]
    if mode == "sim":
        rng = random.Random(5)
        res = []
        for proto in (0, 1, 2):
            for snr in (10, 0, -5):
                ok = bad = 0
                n = 30
                air = 0
                for i in range(n):
                    p = bytes(rng.randrange(256) for _ in range(27))
                    x = encode(p, proto)
                    air = len(x) * 1000 // RATE
                    got = decode(room(x, snr, 1000 * proto + 10 * (snr + 5) + i))
                    if p in got:
                        ok += 1
                    elif got:
                        bad += 1
                rms = math.sqrt(sum(v * v for v in x) / len(x))
                res.append({"proto": proto, "snr_db_16k_equivalent": snr, "frames": n, "ok": ok,
                            "corrupt_accepted": bad, "airtime_ms": air,
                            "tx_rms_full_scale": round(rms, 4)})
        json.dump(res, open(sys.argv[2], "w"), indent=1)
        return 0
    if mode == "tx":
        x = encode(bytes.fromhex(sys.argv[2]), int(sys.argv[3]))
        with wave.open(sys.argv[4], "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in x))
        return 0
    if mode == "rx":
        with wave.open(sys.argv[2], "rb") as w:
            ch = w.getnchannels()
            fr = w.readframes(w.getnframes())
        vals = struct.unpack(f"<{len(fr) // 2}h", fr)[::ch]
        got = decode([v / 32768.0 for v in vals])
        json.dump([g.hex() for g in got], open(sys.argv[3], "w"))
        return 0
    raise SystemExit("mode: sim | tx | rx")


if __name__ == "__main__":
    raise SystemExit(main())
