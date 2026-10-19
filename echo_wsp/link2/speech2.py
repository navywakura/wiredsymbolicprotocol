"""CLAIM2: what happened, not only what it was worth.

    src=YO rel=action dst=EFECTO time=ANTES
    E[V = speaker's Q(s,a), A = mean immediate reward it lived there,
      C = min(100, 10 * own tries)]   domain 'L', generator = speaker
    slot.seq = referent (LINK-1's perceptual digest)

LINK-1 carried V only. At the NOVEL cell the veteran's Q for approach was
+4 while approaching paid -16 on the spot, and the novice paid that first
lesson. A separates the consequence from the value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from echo_wsp.navi10_wsp import pack, unpack

from echo_wsp.link1.speech import ANTES, DOMAIN_LINK, EFECTO, YO
from echo_wsp.link2.envelope import ACT_CLAIM2, Env
from echo_wsp.nexus0.constants import ACTION_REL, N_ACTIONS


def _c100(v: int) -> int:
    return max(-100, min(100, int(v)))


@dataclass(frozen=True)
class Claim2:
    ref: int
    action: int
    value: int  # Q(s, a), clipped ±100
    immediate: int  # mean immediate reward lived, clipped ±100
    support: int  # min(100, 10 * tries)
    sender: int


def postcard(c: Claim2) -> bytes:
    return pack(src=YO, rel=ACTION_REL[c.action], dst=EFECTO, time=ANTES,
                E={"V": _c100(c.value), "A": _c100(c.immediate),
                   "C": max(0, min(100, int(c.support)))},
                domain=DOMAIN_LINK, generator=c.sender & 0xFF,
                slot=(c.ref >> 8) & 0xFF, seq=c.ref & 0xFF)


def env(c: Claim2, seq: int) -> Env:
    return Env(act=ACT_CLAIM2, sender=c.sender & 0xFF, seq=seq & 0xFFFF,
               wsp=postcard(c))


def read(e: Env) -> Optional[Claim2]:
    """Strict: anything not shaped exactly like a CLAIM2 is ignored."""
    if e.act != ACT_CLAIM2:
        return None
    p = unpack(e.wsp)
    if (p["src"], p["dst"], p["time"]) != (YO, EFECTO, ANTES):
        return None
    if p["ext"]["domain"] != DOMAIN_LINK or p["ext"]["generator"] != e.sender:
        return None
    if p["rel"] not in ACTION_REL:
        return None
    a = ACTION_REL.index(p["rel"])
    if not 0 <= a < N_ACTIONS:
        return None
    E = p["E"]
    if E["D"] or E["U"] or E["B"]:
        return None
    if not (-100 <= E["V"] <= 100 and -100 <= E["A"] <= 100 and 0 <= E["C"] <= 100):
        return None
    ref = (p["ext"]["slot"] << 8) | p["ext"]["seq"]
    return Claim2(ref=ref, action=a, value=E["V"], immediate=E["A"],
                  support=E["C"], sender=e.sender)


def gloss(c: Claim2) -> str:
    acts = ("approach", "avoid", "wait")
    return (f"[{c.sender}] en el sitio {c.ref:04x}, {acts[c.action]} me pagó "
            f"{c.immediate:+d} en el acto y vale V{c.value:+d} (soporte {c.support})")
