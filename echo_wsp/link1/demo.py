"""Two ECHO agents talk in WSP, out loud.

    python3 -m echo_wsp.link1.demo                # simulated echo room, 10 dB
    python3 -m echo_wsp.link1.demo --via monitor  # through PipeWire, no air
    python3 -m echo_wsp.link1.demo --via air      # speaker -> microphone

The veteran lives 256 turns in a world. Then they greet each other, the
novice asks about what looks unusual where it is going, the veteran
answers, every postcard crossing the channel as sound, and the novice
lives in the same world with what it heard. Each line printed is the
human mask of a postcard that was actually decoded from samples.
"""

from __future__ import annotations

import argparse
from typing import List

from echo_wsp.link1 import frame as fr
from echo_wsp.link1 import modem, room, speech
from echo_wsp.link1.agent import TalkingAgent, deliver
from echo_wsp.link1.world import LayoutRing
from echo_wsp.nexus0.env import KIND_NAME


class Channel:
    def __init__(self, via: str, snr: float, seed: int) -> None:
        self.via, self.snr, self.seed = via, snr, seed
        self.airtime_ms = 0
        self.sent = self.heard = 0
        if via in ("air", "monitor"):
            from echo_wsp.link1 import audio_io

            self.io = audio_io
            self.state = audio_io.mixer_state()
            if via == "air":
                audio_io.set_mixer({"@DEFAULT_AUDIO_SINK@": ("0.5", False),
                                    "@DEFAULT_AUDIO_SOURCE@": ("1.0", False)})

    def close(self) -> None:
        if self.via in ("air", "monitor"):
            self.io.set_mixer(self.state)

    def send(self, frames: List[fr.Frame]) -> List[fr.Frame]:
        if not frames:
            return []
        x = [0] * 1600 + modem.transmit(frames, 1)
        self.airtime_ms += len(frames) * modem.airtime_ms(1)
        self.sent += len(frames)
        if self.via == "air":
            y = self.io.play_and_record(x, volume=0.35)
        elif self.via == "monitor":
            y = self.io.play_and_record(x, target=self.io.default_sink(),
                                        capture_sink=True, volume=0.5)
        else:
            self.seed += 1
            y = room.simulate(x, snr_db=self.snr, room="echo", seed=self.seed)
        got = [h.frame for h in modem.demodulate(y, 1, max_frames=len(frames) + 8)
               if h.frame is not None]
        self.heard += len(got)
        return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--via", choices=("sim", "monitor", "air"), default="sim")
    ap.add_argument("--snr", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=3)  # a dev world
    args = ap.parse_args(argv)

    world = LayoutRing(args.seed)
    print(f"mundo {args.seed}: " + " ".join(
        f"{i}:{KIND_NAME[k]}" for i, k in enumerate(world.kind) if k))
    vet = TalkingAgent(1, env=LayoutRing(args.seed))
    vet.run(256)
    print(f"veterano: 256 turnos, daño {vet.harm}, primeras lecciones pagadas {vet.first_harm}")

    ch = Channel(args.via, args.snr, args.seed)
    try:
        for f in ch.send([speech.hello_frame(1, 0)]):
            print("  A→B", speech.gloss(f))
        for f in ch.send([speech.hello_frame(2, 0)]):
            print("  B→A", speech.gloss(f))
        nov = TalkingAgent(2, env=LayoutRing(args.seed), audit=True)
        # E5's loop: the novice asks only when it stands in front of
        # something unusual it was never told about. Question and answers
        # both cross the channel; a question lost in the air is never
        # answered and the novice goes on with what it knows.
        nov.env.reset()
        nov.q.reset_traces()
        nov.clear_context()
        for t in range(256):
            q = nov.question_here()
            if q is not None:
                for heard_q in ch.send([q]):
                    print(f"  t{t:03d} B→A", speech.gloss(heard_q))
                    for f in ch.send(vet.hear(heard_q) or []):
                        print(f"  t{t:03d} A→B", speech.gloss(f))
                        deliver(nov, [f])
            nov.turn(t)
        silent = TalkingAgent(2, env=LayoutRing(args.seed))
        silent.run(256)
    finally:
        ch.close()
    print(f"canal {args.via}: {ch.sent} postales enviadas, {ch.heard} oídas, "
          f"{ch.airtime_ms / 1000:.1f} s de sonido")
    print(f"novato con lo oído: primeras lecciones pagadas {nov.first_harm}, daño {nov.harm}")
    print(f"novato en silencio: primeras lecciones pagadas {silent.first_harm}, daño {silent.harm}")
    r = nov.report()
    print("firewall:", {k: r[k] for k in ("false_facts", "destroyed", "cortex_calls",
                                          "foreign_q_writes", "foreign_t_writes",
                                          "foreign_cam_allocs", "unexplained_diversions")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
