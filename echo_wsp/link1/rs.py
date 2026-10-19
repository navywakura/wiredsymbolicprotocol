"""Reed-Solomon RS(15, 11) over GF(16). Integers only.

One code symbol is one nibble, and one nibble is what a single MFSK tone
carries, so a tone heard wrong is exactly one symbol error. 4 parity
symbols correct any 2 wrong symbols in a block of 15.

GF(16) is built on the primitive polynomial x^4 + x + 1. The generator has
roots alpha^1 .. alpha^4 (first consecutive root 1). Polynomials are lists
of coefficients, lowest degree first.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

N = 15
K = 11
NSYM = N - K  # 4 parity symbols, t = 2
PRIM = 0b10011

EXP = [0] * 30
LOG = [0] * 16
_x = 1
for _i in range(15):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x10:
        _x ^= PRIM
for _i in range(15, 30):
    EXP[_i] = EXP[_i - 15]


def mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return EXP[LOG[a] + LOG[b]]


def div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("GF(16) division by zero")
    if a == 0:
        return 0
    return EXP[(LOG[a] - LOG[b]) % 15]


def inv(a: int) -> int:
    return div(1, a)


def pow_a(e: int) -> int:
    return EXP[e % 15]


def poly_mul(p: List[int], q: List[int]) -> List[int]:
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        if a == 0:
            continue
        for j, b in enumerate(q):
            out[i + j] ^= mul(a, b)
    return out


def poly_eval(p: List[int], x: int) -> int:
    """Horner, lowest degree first."""
    y = 0
    for c in reversed(p):
        y = mul(y, x) ^ c
    return y


def _generator() -> List[int]:
    g = [1]
    for i in range(1, NSYM + 1):
        g = poly_mul(g, [pow_a(i), 1])  # (x + alpha^i)
    return g


GEN = _generator()  # degree 4, monic


def encode(msg: List[int]) -> List[int]:
    """11 data nibbles -> 15 code nibbles, systematic: data then parity.

    Codeword index j is the coefficient of x^(14 - j), so the data come
    first on the air in the order they were given.
    """
    if len(msg) != K or any(not 0 <= m <= 15 for m in msg):
        raise ValueError("RS(15,11) takes 11 nibbles")
    # c(x) = m(x) * x^4 + (m(x) * x^4 mod g(x)); work highest degree first.
    rem = [0] * NSYM
    g_hi = list(reversed(GEN))  # highest first, g_hi[0] == 1
    for m in msg:
        f = m ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for j in range(NSYM):
                rem[j] ^= mul(f, g_hi[j + 1])
    return list(msg) + rem


def _syndromes(code: List[int]) -> List[int]:
    # code[j] is the coefficient of x^(14-j)
    poly = list(reversed(code))
    return [poly_eval(poly, pow_a(i)) for i in range(1, NSYM + 1)]


def _bm(synd: List[int]) -> Tuple[List[int], int]:
    """Berlekamp-Massey over a syndrome list -> (locator, L), lowest first."""
    lam = [1]
    prev = [1]
    L = 0
    m = 1
    b = 1
    for n in range(len(synd)):
        d = synd[n]
        for i in range(1, L + 1):
            if i < len(lam):
                d ^= mul(lam[i], synd[n - i])
        if d == 0:
            m += 1
            continue
        coef = div(d, b)
        shifted = [0] * m + [mul(coef, c) for c in prev]
        new = [0] * max(len(lam), len(shifted))
        for i, c in enumerate(lam):
            new[i] ^= c
        for i, c in enumerate(shifted):
            new[i] ^= c
        if 2 * L <= n:
            prev = lam
            L = n + 1 - L
            b = d
            m = 1
        else:
            m += 1
        lam = new
    while len(lam) > 1 and lam[-1] == 0:
        lam.pop()
    return lam, L


def decode(code: List[int], erasures: Sequence[int] = ()) -> Tuple[Optional[List[int]], int]:
    """Return (11 data nibbles, symbols changed) or (None, -1) on failure.

    `erasures` are codeword indices the caller does not trust. With e of
    them, up to t more unknown errors are fixed as long as 2t + e <= 4
    (Forney syndromes, then Berlekamp-Massey on the remaining 4 - e).
    Failure is reported, never guessed; with 4 erasures there is no
    redundancy left to check, so the frame CRC upstream is the judge.
    """
    if len(code) != N or any(not 0 <= c <= 15 for c in code):
        raise ValueError("RS(15,11) takes 15 nibbles")
    era = sorted(set(int(j) for j in erasures))
    if any(not 0 <= j < N for j in era) or len(era) > NSYM:
        raise ValueError("at most 4 erasures, inside the block")
    synd = _syndromes(code)
    if not any(synd):
        return list(code[:K]), 0
    e = len(era)
    gamma = [1]
    for j in era:
        gamma = poly_mul(gamma, [1, pow_a(N - 1 - j)])  # (1 + X_j x)
    forney = poly_mul(synd, gamma)[:NSYM]
    lam, L = _bm(forney[e:])
    if 2 * L + e > NSYM or len(lam) - 1 != L:
        return None, -1
    psi = poly_mul(lam, gamma)  # errata locator: errors and erasures
    while len(psi) > 1 and psi[-1] == 0:
        psi.pop()
    deg = len(psi) - 1

    # Chien search: a root at alpha^(-p) means errata at power p, which
    # is codeword index 14 - p.
    positions = [p for p in range(N) if poly_eval(psi, pow_a(-p)) == 0]
    if len(positions) != deg:
        return None, -1

    # Forney with first consecutive root 1: e = Omega(X^-1) / Psi'(X^-1).
    omega = poly_mul(synd, psi)[:NSYM]
    psi_d = [psi[i] if i % 2 == 1 else 0 for i in range(1, len(psi))]
    fixed = list(code)
    changed = 0
    for p in positions:
        x_inv = pow_a(-p)
        den = poly_eval(psi_d, x_inv)
        if den == 0:
            return None, -1
        mag = div(poly_eval(omega, x_inv), den)
        if mag:
            fixed[N - 1 - p] ^= mag
            changed += 1
    if any(_syndromes(fixed)):
        return None, -1
    return fixed[:K], changed
