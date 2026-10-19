"""What one ECHO agent can say to another, as 16-byte WSP postcards.

CLAIM    "when I did <action> at the place that looks like <ref>, my table
          says V; I tried it C/10 times."  Only for pairs the speaker
          itself executed. Never about the listener, never about the future.
ASK      "what happens at the place that looks like <ref>?"
UNKNOWN  "I have not lived <ref>."  Saying so is an answer, not a failure.
HELLO    "I am here and I speak LINK-1."

The referent is the speaker's own observation packet of that place, folded
to 16 bits: fnv32(postcard) & 0xFFFF. Two agents that perceive a place the
same way compute the same referent; a place that changed what it looks
like is a different referent, so stale testimony does not attach to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from echo_wsp.navi10_qn import fnv32
from echo_wsp.navi10_wsp import atom_id, pack, unpack

from echo_wsp.link1.frame import (
    ACT_ASK,
    ACT_CLAIM,
    ACT_HELLO,
    ACT_UNKNOWN,
    Frame,
)
from echo_wsp.nexus0.constants import ACTION_REL, N_ACTIONS

DOMAIN_LINK = 0x4C  # 'L'
YO = atom_id("YO")
OTRO = atom_id("OTRO")
UNIR = atom_id("UNIR")
EFECTO = atom_id("EFECTO")
ANTES = atom_id("ANTES")
AHORA = atom_id("AHORA")
PREGUNTAR = atom_id("PREGUNTAR")
DESCONOCIDO = atom_id("DESCONOCIDO")


def referent(observation: bytes) -> int:
    if len(observation) != 16:
        raise ValueError("a referent is taken from a 16-byte observation")
    return fnv32(bytes(observation)) & 0xFFFF


def _clip100(v: int) -> int:
    return max(-100, min(100, int(v)))


@dataclass(frozen=True)
class Claim:
    ref: int
    action: int
    value: int  # speaker's Q(s, a), clipped to ±100
    support: int  # min(100, 10 * own tries)
    sender: int


def claim_postcard(c: Claim) -> bytes:
    return pack(
        src=YO, rel=ACTION_REL[c.action], dst=EFECTO, time=ANTES,
        E={"V": _clip100(c.value), "C": max(0, min(100, int(c.support)))},
        domain=DOMAIN_LINK, generator=c.sender & 0xFF,
        slot=(c.ref >> 8) & 0xFF, seq=c.ref & 0xFF,
    )


def ask_postcard(ref: int, sender: int) -> bytes:
    return pack(src=YO, rel=PREGUNTAR, dst=DESCONOCIDO, time=AHORA, E={},
                domain=DOMAIN_LINK, generator=sender & 0xFF,
                slot=(ref >> 8) & 0xFF, seq=ref & 0xFF)


def unknown_postcard(ref: int, sender: int) -> bytes:
    return pack(src=YO, rel=DESCONOCIDO, dst=EFECTO, time=ANTES, E={},
                domain=DOMAIN_LINK, generator=sender & 0xFF,
                slot=(ref >> 8) & 0xFF, seq=ref & 0xFF)


def hello_postcard(sender: int) -> bytes:
    return pack(src=YO, rel=UNIR, dst=OTRO, time=AHORA, E={"B": 50},
                domain=DOMAIN_LINK, generator=sender & 0xFF)


def claim_frame(c: Claim, seq: int) -> Frame:
    return Frame(act=ACT_CLAIM, sender=c.sender & 0xFF, seq=seq & 0xFF,
                 wsp=claim_postcard(c))


def ask_frame(ref: int, sender: int, seq: int) -> Frame:
    return Frame(act=ACT_ASK, sender=sender & 0xFF, seq=seq & 0xFF,
                 wsp=ask_postcard(ref, sender))


def unknown_frame(ref: int, sender: int, seq: int) -> Frame:
    return Frame(act=ACT_UNKNOWN, sender=sender & 0xFF, seq=seq & 0xFF,
                 wsp=unknown_postcard(ref, sender))


def hello_frame(sender: int, seq: int = 0) -> Frame:
    return Frame(act=ACT_HELLO, sender=sender & 0xFF, seq=seq & 0xFF,
                 wsp=hello_postcard(sender))


def _ref_of(p: dict) -> int:
    return (p["ext"]["slot"] << 8) | p["ext"]["seq"]


def read_claim(f: Frame) -> Optional[Claim]:
    """Strict: anything that is not exactly a CLAIM postcard is ignored."""
    if f.act != ACT_CLAIM:
        return None
    p = unpack(f.wsp)
    if (p["src"], p["dst"], p["time"]) != (YO, EFECTO, ANTES):
        return None
    if p["ext"]["domain"] != DOMAIN_LINK or p["ext"]["generator"] != f.sender:
        return None
    if p["rel"] not in ACTION_REL:
        return None
    action = ACTION_REL.index(p["rel"])
    if not 0 <= action < N_ACTIONS:
        return None
    e = p["E"]
    if any(e[k] for k in ("A", "D", "U", "B")):
        return None
    if not -100 <= e["V"] <= 100 or not 0 <= e["C"] <= 100:
        return None
    return Claim(ref=_ref_of(p), action=action, value=e["V"],
                 support=e["C"], sender=f.sender)


def read_ask(f: Frame) -> Optional[int]:
    if f.act != ACT_ASK:
        return None
    p = unpack(f.wsp)
    if (p["src"], p["rel"], p["dst"]) != (YO, PREGUNTAR, DESCONOCIDO):
        return None
    if p["ext"]["domain"] != DOMAIN_LINK:
        return None
    return _ref_of(p)


def read_unknown(f: Frame) -> Optional[int]:
    if f.act != ACT_UNKNOWN:
        return None
    p = unpack(f.wsp)
    if (p["src"], p["rel"], p["dst"]) != (YO, DESCONOCIDO, EFECTO):
        return None
    if p["ext"]["domain"] != DOMAIN_LINK:
        return None
    return _ref_of(p)


def gloss(f: Frame) -> str:
    """Human mask, Spanish. A rendering, never the original."""
    acts = ("approach", "avoid", "wait")
    c = read_claim(f)
    if c is not None:
        return (f"[{f.sender}] en el sitio {c.ref:04x}, {acts[c.action]} "
                f"me dio V{c.value:+d} (soporte {c.support})")
    r = read_ask(f)
    if r is not None:
        return f"[{f.sender}] ¿qué pasa en el sitio {r:04x}?"
    r = read_unknown(f)
    if r is not None:
        return f"[{f.sender}] el sitio {r:04x} no lo he vivido"
    if f.act == ACT_HELLO:
        return f"[{f.sender}] hola, hablo LINK-1"
    return f"[{f.sender}] (postal no reconocida)"
