"""Envelope v2: one WSP postcard, authenticated. 27 bytes, integers only.

    off size field
      0   1   magic 'W' (0x57)
      1   1   version 2 (high nibble) | act (low nibble)
      2   1   sender id
      3   2   sequence, 16 bits big-endian, strictly increasing per sender
      5  16   WSP postcard, navi10_wsp.pack layout, untouched
     21   4   tag = HMAC-SHA256(key, session || bytes 0..20)[:4]
     25   2   CRC-16/CCITT-FALSE over bytes 0..24

The session (8 bytes) never travels: sender and listener share it, so a
recording from another session does not verify. The CRC filters the air,
the MAC filters impostors; both are checked. A 32-bit tag means 2^-32 per
forgery attempt: a laboratory, not a product.

On the air: 54 nibbles + 1 zero pad = 55 = five RS(15,11) blocks = 75 code
symbols, interleaved and whitened with LINK-1's LFSR, continued.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import List, Optional, Tuple

from echo_wsp.link1 import rs
from echo_wsp.link1.frame import crc16, from_nibbles, to_nibbles

MAGIC = 0x57
VERSION = 2
WSP_BYTES = 16
TAG_BYTES = 4
SESSION_BYTES = 8
ENV_BYTES = 5 + WSP_BYTES + TAG_BYTES + 2  # 27
DATA_NIBBLES = 2 * ENV_BYTES  # 54
BLOCKS = 5
PAD = BLOCKS * rs.K - DATA_NIBBLES  # 1
AIR_SYMBOLS = BLOCKS * rs.N  # 75

ACT_HELLO = 0
ACT_CLAIM2 = 5
ACT_ASK = 2
ACT_UNKNOWN = 3


def _whitening(n: int) -> tuple:
    """LINK-1's LFSR (x^16+x^14+x^13+x^11+1, seed 0xACE1), n nibbles."""
    reg = 0xACE1
    out = []
    for _ in range(n):
        nib = 0
        for _ in range(4):
            bit = ((reg >> 0) ^ (reg >> 2) ^ (reg >> 3) ^ (reg >> 5)) & 1
            reg = (reg >> 1) | (bit << 15)
            nib = (nib << 1) | (reg & 1)
        out.append(nib)
    return tuple(out)


WHITEN = _whitening(AIR_SYMBOLS)


@dataclass(frozen=True)
class Env:
    act: int
    sender: int
    seq: int
    wsp: bytes

    def __post_init__(self) -> None:
        if type(self.act) is not int or not 0 <= self.act <= 15:
            raise ValueError("act must be a nibble")
        if type(self.sender) is not int or not 0 <= self.sender <= 255:
            raise ValueError("sender must be a byte")
        if type(self.seq) is not int or not 0 <= self.seq <= 0xFFFF:
            raise ValueError("seq must fit 16 bits")
        if not isinstance(self.wsp, (bytes, bytearray)) or len(self.wsp) != WSP_BYTES:
            raise ValueError("a postcard is exactly 16 bytes")


def tag(key: bytes, session: bytes, head: bytes) -> bytes:
    if len(session) != SESSION_BYTES:
        raise ValueError("session is 8 bytes")
    return hmac.new(key, session + head, hashlib.sha256).digest()[:TAG_BYTES]


def seal(e: Env, key: bytes, session: bytes) -> bytes:
    head = bytes([MAGIC, (VERSION << 4) | e.act, e.sender]) + e.seq.to_bytes(2, "big") + bytes(e.wsp)
    body = head + tag(key, session, head)
    return body + crc16(body).to_bytes(2, "big")


# Why a frame was refused. The listener only ever sees OK frames.
OK = "ok"
BAD_SHAPE = "bad_shape"
BAD_CRC = "bad_crc"
UNKNOWN_SENDER = "unknown_sender"
BAD_MAC = "bad_mac"
REPLAY = "replay"


def open_(raw: bytes, keyring: dict, session: bytes) -> Tuple[Optional[Env], str]:
    """Check CRC, then the sender's MAC. Replay is the Guard's job."""
    if len(raw) != ENV_BYTES or raw[0] != MAGIC or (raw[1] >> 4) != VERSION:
        return None, BAD_SHAPE
    if crc16(raw[:25]) != int.from_bytes(raw[25:27], "big"):
        return None, BAD_CRC
    key = keyring.get(raw[2])
    if key is None:
        return None, UNKNOWN_SENDER
    if not hmac.compare_digest(tag(key, session, raw[:21]), raw[21:25]):
        return None, BAD_MAC
    return Env(act=raw[1] & 0x0F, sender=raw[2],
               seq=int.from_bytes(raw[3:5], "big"), wsp=bytes(raw[5:21])), OK


class Guard:
    """Keyring + session + per-sender replay window (strictly increasing)."""

    def __init__(self, keyring: dict, session: bytes) -> None:
        self.keyring = dict(keyring)
        self.session = bytes(session)
        self.last: dict = {}
        self.refused: dict = {}

    def admit(self, raw: bytes) -> Optional[Env]:
        e, why = open_(raw, self.keyring, self.session)
        if e is not None and e.seq <= self.last.get(e.sender, -1):
            e, why = None, REPLAY
        if e is None:
            self.refused[why] = self.refused.get(why, 0) + 1
            return None
        self.last[e.sender] = e.seq
        return e


def to_air(raw: bytes) -> List[int]:
    if len(raw) != ENV_BYTES:
        raise ValueError("envelope v2 is 27 bytes")
    nib = to_nibbles(raw) + [0] * PAD
    blocks = [rs.encode(nib[b * rs.K:(b + 1) * rs.K]) for b in range(BLOCKS)]
    return [blocks[i % BLOCKS][i // BLOCKS] ^ WHITEN[i] for i in range(AIR_SYMBOLS)]


def from_air(symbols: List[int], doubt: Optional[List[int]] = None):
    """75 heard nibbles -> (27 bytes, symbols changed) or (None, -1). GMD as LINK-1."""
    if len(symbols) != AIR_SYMBOLS:
        raise ValueError("expected 75 symbols")
    blocks = [[0] * rs.N for _ in range(BLOCKS)]
    bdoubt = [[0] * rs.N for _ in range(BLOCKS)]
    for i, s in enumerate(symbols):
        blocks[i % BLOCKS][i // BLOCKS] = s ^ WHITEN[i]
        if doubt is not None:
            bdoubt[i % BLOCKS][i // BLOCKS] = doubt[i]
    nib: List[int] = []
    fixed = 0
    for blk, dbt in zip(blocks, bdoubt):
        data, n = rs.decode(blk)
        if data is None and doubt is not None:
            order = sorted(range(rs.N), key=lambda j: (-dbt[j], j))
            for e in range(1, rs.NSYM + 1):
                data, n = rs.decode(blk, erasures=order[:e])
                if data is not None:
                    break
        if data is None:
            return None, -1
        nib.extend(data)
        fixed += n
    if any(nib[DATA_NIBBLES:]):  # the pad must decode as zero
        return None, -1
    return from_nibbles(nib[:DATA_NIBBLES]), fixed


def test_key(name: str) -> bytes:
    """A declared TEST key, derived from public text. Not a secret."""
    return hashlib.sha256(b"LINK-2 test key, not a secret: " + name.encode()).digest()


def test_session(name: str) -> bytes:
    return hashlib.sha256(b"LINK-2 test session: " + name.encode()).digest()[:SESSION_BYTES]
