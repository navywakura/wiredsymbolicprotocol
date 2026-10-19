"""The link envelope around one WSP postcard. 22 bytes, integers only.

    off size field
      0   1   magic 'W' (0x57)
      1   1   version (high nibble, 1) | act (low nibble)
      2   1   sender id
      3   1   message sequence (mod 256)
      4  16   WSP postcard, navi10_wsp.pack layout, untouched
     20   2   CRC-16/CCITT-FALSE over bytes 0..19, big-endian

There is no "verified" bit and no authority field: whatever arrives on a
link is testimony, and the receiver decides what that is worth. The
postcard keeps sizeof == 16; the envelope is around it, never inside.

On the air the 22 bytes become 44 nibbles, split into four RS(15,11)
blocks, interleaved symbol by symbol (a burst of up to 8 wrong tones costs
each block at most 2) and whitened with a fixed LFSR sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from echo_wsp.navi10_qn import WSP_BYTES

from echo_wsp.link1 import rs

MAGIC = 0x57
VERSION = 1
FRAME_BYTES = 4 + WSP_BYTES + 2  # 22
FRAME_NIBBLES = 2 * FRAME_BYTES  # 44
BLOCKS = FRAME_NIBBLES // rs.K  # 4
AIR_SYMBOLS = BLOCKS * rs.N  # 60

ACT_HELLO = 0
ACT_CLAIM = 1
ACT_ASK = 2
ACT_UNKNOWN = 3
ACT_BYE = 4
ACT_NAMES = {ACT_HELLO: "HELLO", ACT_CLAIM: "CLAIM", ACT_ASK: "ASK",
             ACT_UNKNOWN: "UNKNOWN", ACT_BYE: "BYE"}

assert FRAME_NIBBLES == BLOCKS * rs.K, "envelope must fill RS blocks exactly"


def _whitening() -> tuple:
    """60 nibbles from a 16-bit Fibonacci LFSR x^16+x^14+x^13+x^11+1, seed 0xACE1.

    A postcard is mostly the same few bytes (magic, atoms, zero axes), so
    without this the same nibble rides the same tone in every frame; when
    a room notches that tone every frame dies in the same places and a
    retry dies the same way. XOR with a fixed pseudo-random sequence
    spreads any content over all sixteen tones. Integers only.
    """
    reg = 0xACE1
    out = []
    for _ in range(AIR_SYMBOLS):
        nib = 0
        for _ in range(4):
            bit = ((reg >> 0) ^ (reg >> 2) ^ (reg >> 3) ^ (reg >> 5)) & 1
            reg = (reg >> 1) | (bit << 15)
            nib = (nib << 1) | (reg & 1)
        out.append(nib)
    return tuple(out)


WHITEN = _whitening()


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


@dataclass(frozen=True)
class Frame:
    act: int
    sender: int
    seq: int
    wsp: bytes

    def __post_init__(self) -> None:
        if type(self.act) is not int or not 0 <= self.act <= 15:
            raise ValueError("act must be a nibble")
        if type(self.sender) is not int or not 0 <= self.sender <= 255:
            raise ValueError("sender must be a byte")
        if type(self.seq) is not int or not 0 <= self.seq <= 255:
            raise ValueError("seq must be a byte")
        if not isinstance(self.wsp, (bytes, bytearray)) or len(self.wsp) != WSP_BYTES:
            raise ValueError("a postcard is exactly 16 bytes")

    def to_bytes(self) -> bytes:
        head = bytes([MAGIC, (VERSION << 4) | self.act, self.sender, self.seq])
        body = head + bytes(self.wsp)
        return body + crc16(body).to_bytes(2, "big")


def parse(raw: bytes) -> Optional[Frame]:
    """Bytes -> Frame, or None. A bad frame is silence, not a guess."""
    if len(raw) != FRAME_BYTES:
        return None
    if raw[0] != MAGIC or (raw[1] >> 4) != VERSION:
        return None
    if crc16(raw[:20]) != int.from_bytes(raw[20:22], "big"):
        return None
    return Frame(act=raw[1] & 0x0F, sender=raw[2], seq=raw[3], wsp=bytes(raw[4:20]))


def to_nibbles(raw: bytes) -> List[int]:
    out = []
    for b in raw:
        out.append(b >> 4)
        out.append(b & 0x0F)
    return out


def from_nibbles(nib: List[int]) -> bytes:
    if len(nib) % 2:
        raise ValueError("odd nibble count")
    return bytes((nib[i] << 4) | nib[i + 1] for i in range(0, len(nib), 2))


def to_air(raw: bytes) -> List[int]:
    """22 bytes -> 60 interleaved code nibbles."""
    if len(raw) != FRAME_BYTES:
        raise ValueError("frame must be 22 bytes")
    nib = to_nibbles(raw)
    blocks = [rs.encode(nib[b * rs.K:(b + 1) * rs.K]) for b in range(BLOCKS)]
    return [blocks[i % BLOCKS][i // BLOCKS] ^ WHITEN[i] for i in range(AIR_SYMBOLS)]


def from_air(symbols: List[int],
             doubt: Optional[List[int]] = None) -> Tuple[Optional[bytes], int]:
    """60 heard nibbles -> (22 bytes, symbols changed) or (None, -1).

    `doubt[i]` ranks how unsure the modem was of symbol i (higher = less
    sure). A block that fails errors-only decoding is retried with its
    1, 2, 3 and 4 least sure symbols erased: generalised minimum-distance
    decoding (Forney, 1966). Each block keeps its first success; the frame
    CRC then accepts or refuses the whole frame.
    """
    if len(symbols) != AIR_SYMBOLS:
        raise ValueError("expected 60 symbols")
    if doubt is not None and len(doubt) != AIR_SYMBOLS:
        raise ValueError("expected 60 doubt values")
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
    return from_nibbles(nib), fixed
