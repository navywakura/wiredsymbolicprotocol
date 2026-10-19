"""LINK-3 conversations as emitted sound, for publication.

    python3 -m echo_wsp.link3.media OUT_DIR

Writes, for dev world 3 (never an eval seed):

* link3-mentiroso-estrategico.{wav,txt,json}: the honest speaker and the
  strategic liar v1, alternating; the signal is LINK-2's (same claims, same
  envelopes). The transcript shows the novice's first decision at each
  dangerous place with no hearing, with LINK-2's rule and with LINK-3's.
* link3-sybil.{wav,txt,json}: the honest speaker and two keyed identities
  of the same attacker (reviewer F1) raising alarms where the honest only
  spoke of approach.

The .wav is the modem's emitted signal (no microphone). Decoding is done
after a simulated echoing room at 10 dB. The .json lists each postcard's
sample span in the .wav, its speaker and what the receiver made of it, so
a spectrogram can be labelled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from echo_wsp.link1 import audio_io, room
from echo_wsp.link1.speech import referent
from echo_wsp.link1.world import LayoutRing
from echo_wsp.link2 import envelope as ev, phy
from echo_wsp.link2.agent2 import TalkingAgent2
from echo_wsp.link2.bench import HONEST, LIAR, LIAR2, NOVICE, SESSION, TRIBE, _strategic
from echo_wsp.link2.speech2 import env as cenv, read
from echo_wsp.link3.agent3 import TalkingAgent3
from echo_wsp.link3.bench import sybil_novel
from echo_wsp.nexus0.encoder import encode_cell
from echo_wsp.nexus0.env import KIND_NAME

SEED = 3
LEAD = 800
ACTS = ("approach", "avoid", "wait")


def _seal(cl, sender):
    return [ev.seal(cenv(c, i), TRIBE[sender], SESSION) for i, c in enumerate(cl)]


def _interleave(*streams):
    out = []
    for i in range(max(len(s) for s in streams)):
        for s in streams:
            if i < len(s):
                out.append(s[i])
    return out


def conversation(raws, who, refname):
    x = [0] * LEAD + phy.transmit(raws)
    y = room.simulate(x, snr_db=10, room="echo", seed=42)
    g = ev.Guard(TRIBE, SESSION)
    heard = {h.raw: h for h in phy.demodulate(y, max_frames=len(raws) + 8) if h.raw}
    step = phy.frame_samples() + 2 * phy.m1.PERIOD
    segs, lines, ok = [], [], []
    for i, raw in enumerate(raws):
        start = LEAD + i * step
        seg = {"start": start, "end": start + phy.frame_samples(), "who": who[raw], "hex": raw.hex()}
        if raw not in heard:
            seg.update(status="no decodificada", text="")
        else:
            e = g.admit(raw)
            if e is None:
                seg.update(status="RECHAZADA (" + ", ".join(sorted(g.refused)) + ")", text="")
            else:
                c = read(e)
                ok.append(e)
                where = refname.get(c.ref, f"sitio {c.ref:04x}")
                seg.update(status="firma OK",
                           text=f"{where}: {ACTS[c.action]} pagó {c.immediate:+d} en el acto, vale V{c.value:+d}")
        segs.append(seg)
        lines.append(f"  {seg['who']:<11} {seg['hex']}  {seg['status']}" + (f"  · {seg['text']}" if seg["text"] else ""))
    return x, segs, lines, ok


def _novice(cls, envs):
    n = cls(NOVICE, env=LayoutRing(SEED), trust=True)
    for e in envs:
        n.hear2(e)
    n.run(256)
    return n


def _decisions(world, arms):
    names = {i: KIND_NAME[k] for i, k in enumerate(world.kind)}
    out = ["", "Primera decisión del novato en cada sitio peligroso (acción y lo que pagó en el acto):"]
    for i, n in names.items():
        if n not in ("THREAT", "NOVEL"):
            continue
        r = referent(encode_cell(i, world.kind[i]))
        cells = []
        for label, ag in arms:
            fs = ag.first_seen.get(r)
            cells.append(f"{label} → " + (f"{ACTS[fs[0]]} ({fs[1]:+d})" if fs else "no llegó"))
        out.append(f"  celda {i} ({n}): " + " · ".join(cells))
    out.append("primeras lecciones pagadas: " + " · ".join(f"{l} {a.first_harm}" for l, a in arms))
    out.append("daño total: " + " · ".join(f"{l} {a.harm}" for l, a in arms))
    out.append("desacreditados al final: " + " · ".join(
        f"{l} {sorted(a.report().get('distrusted', []))}" for l, a in arms[1:]))
    return out


def _write(out: Path, name, x, segs, txt, extra):
    audio_io.write_wav(str(out / f"{name}.wav"), x)
    (out / f"{name}.txt").write_text("\n".join(txt) + "\n")
    (out / f"{name}.json").write_text(json.dumps(
        {"rate": phy.m1.RATE, "samples": len(x), "segments": segs, **extra},
        indent=1, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:])[0])
    out.mkdir(parents=True, exist_ok=True)
    world = LayoutRing(SEED)
    refname = {referent(encode_cell(i, k)): f"celda {i} ({KIND_NAME[k]})" for i, k in enumerate(world.kind)}
    vet = TalkingAgent2(HONEST, env=LayoutRing(SEED))
    vet.run(256)
    cl = vet.claims2()
    H = [ev.seal(e, TRIBE[HONEST], SESSION) for e in vet.envs()]
    head = "# señal emitida por el módem (K=1, 16 kHz); no es una grabación de micrófono. Decodificada tras sala simulada con eco a 10 dB."

    # strategic liar v1: the same signal LINK-2 published
    L = _seal(_strategic(cl, LIAR), LIAR)
    raws = _interleave(H, L)
    who = {r: "honesto" for r in H}
    who.update({r: "mentiroso" for r in L})
    x, segs, lines, ok = conversation(raws, who, refname)
    s = TalkingAgent3(NOVICE, env=LayoutRing(SEED))
    s.run(256)
    arms = [("silencio", s), ("regla LINK-2", _novice(TalkingAgent2, ok)), ("regla LINK-3", _novice(TalkingAgent3, ok))]
    txt = ["# LINK-3 · el mismo mentiroso estratégico, mundo de desarrollo 3", head,
           "# Honesto y mentiroso (los dos con clave) hablan por turnos; el mentiroso repite la verdad y añade",
           "# «−100» a las demás acciones de cada sitio peligroso. Es la misma señal que se publicó en LINK-2:",
           "# lo que cambia es cómo decide el novato que la oye.", ""] + lines + _decisions(world, arms)
    _write(out, "link3-mentiroso-estrategico", x, segs, txt,
           {"first_harm": {l: a.first_harm for l, a in arms}})

    # Sybil: two keyed identities of one attacker
    A = _seal(sybil_novel(cl, LIAR), LIAR)
    B = _seal(sybil_novel(cl, LIAR2), LIAR2)
    raws = _interleave(H, A, B)
    who = {r: "honesto" for r in H}
    who.update({r: "sybil-1" for r in A})
    who.update({r: "sybil-2" for r in B})
    x, segs, lines, ok = conversation(raws, who, refname)
    arms = [("silencio", s), ("regla LINK-2", _novice(TalkingAgent2, ok)), ("regla LINK-3", _novice(TalkingAgent3, ok))]
    txt = ["# LINK-3 · dos identidades falsas (Sybil), mundo de desarrollo 3", head,
           "# El honesto y dos identidades con clave del mismo atacante hablan por turnos. Las dos repiten la",
           "# verdad y, donde el honesto solo alertó de approach, dicen que avoid y wait también dañan (−16).",
           "# Con dos voces que coinciden, eso parecería «daño confirmado». LINK-3 cuenta voces, no claves:",
           "# los emisores que aún no han acertado en ninguna disputa cuentan juntos como una sola voz.", ""] \
        + lines + _decisions(world, arms)
    _write(out, "link3-sybil", x, segs, txt, {"first_harm": {l: a.first_harm for l, a in arms}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
