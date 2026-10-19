"""Capa I extendida (v0.5): plano científico del núcleo semántico.

El núcleo de 32 átomos es un contrato binario congelado (5 bits) y
seguirá siéndolo. Este módulo abre un **plano de extensión** en los
códigos 32..127 —el bit alto sigue reservado al marcador de concepto
derivado (0x80)— con los primitivos que hacen falta para hablar de
física, química y matemáticas sin recurrir a vocabulario humano.

Tres piezas:

1. `SciPrimitive` — átomos de dominio (magnitudes, operadores, cuerpos).
2. `Dimension`   — vector de 7 exponentes SI (M L T Θ I N J). Dos
   especies no comparten palabras, pero sí comparten dimensiones: la
   masa es masa en Erid y en la Tierra.
3. `Quantity` y `Element` — una cantidad física es mantisa + exponente
   + dimensión; un elemento **es** su número atómico Z. El símbolo "C"
   o la palabra "carbono" son máscaras humanas, no el dato.

Todo entero viaja en binario puro, así que la codificación es agnóstica
respecto a la base numérica del emisor: una especie que cuente en base 6
lee el mismo entero que una que cuente en base 10.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .primitives import normalize_token

# El plano científico empieza justo después del núcleo congelado.
SCI_BASE = 32
SCI_MAX = 127


class SciCategory(str, Enum):
    MAGNITUDE = "magnitude"   # dimensiones físicas fundamentales
    OPERATOR = "operator"     # relaciones matemáticas
    STRUCTURE = "structure"   # materia y cuerpos
    NUMBER = "number"         # constructos numéricos


class SciPrimitive(Enum):
    """Átomos del plano científico. El valor del enum es su código de byte."""

    # -- magnitudes (base dimensional) ------------------------------------
    MASA = (32, "masa", "mass", SciCategory.MAGNITUDE)
    LONGITUD = (33, "longitud", "length", SciCategory.MAGNITUDE)
    DURACION = (34, "duración", "duration", SciCategory.MAGNITUDE)
    TEMPERATURA = (35, "temperatura", "temperature", SciCategory.MAGNITUDE)
    CARGA = (36, "carga", "charge", SciCategory.MAGNITUDE)
    CANTIDAD = (37, "cantidad", "amount", SciCategory.MAGNITUDE)
    LUMINOSIDAD = (38, "luminosidad", "luminosity", SciCategory.MAGNITUDE)
    # -- magnitudes derivadas de uso frecuente ------------------------------
    ENERGIA = (39, "energía", "energy", SciCategory.MAGNITUDE)
    VELOCIDAD = (40, "velocidad", "speed", SciCategory.MAGNITUDE)
    FRECUENCIA = (41, "frecuencia", "frequency", SciCategory.MAGNITUDE)
    PRESION = (42, "presión", "pressure", SciCategory.MAGNITUDE)
    DENSIDAD = (43, "densidad", "density", SciCategory.MAGNITUDE)
    # -- operadores matemáticos ----------------------------------------------
    IGUAL = (48, "igual", "equal", SciCategory.OPERATOR)
    MAYOR = (49, "mayor", "greater", SciCategory.OPERATOR)
    MENOR = (50, "menor", "less", SciCategory.OPERATOR)
    PROPORCIONAL = (51, "proporcional", "proportional", SciCategory.OPERATOR)
    SUMA = (52, "suma", "sum", SciCategory.OPERATOR)
    RESTA = (53, "resta", "difference", SciCategory.OPERATOR)
    PRODUCTO = (54, "producto", "product", SciCategory.OPERATOR)
    COCIENTE = (55, "cociente", "quotient", SciCategory.OPERATOR)
    POTENCIA = (56, "potencia", "power", SciCategory.OPERATOR)
    RAIZ = (57, "raíz", "root", SciCategory.OPERATOR)
    APROXIMADO = (58, "aproximado", "approximately", SciCategory.OPERATOR)
    NEGATIVO = (59, "negativo", "negative", SciCategory.OPERATOR)
    # -- estructura de la materia y del cosmos --------------------------------
    ATOMO = (64, "átomo", "atom", SciCategory.STRUCTURE)
    MOLECULA = (65, "molécula", "molecule", SciCategory.STRUCTURE)
    ONDA = (66, "onda", "wave", SciCategory.STRUCTURE)
    LUZ = (67, "luz", "light", SciCategory.STRUCTURE)
    ESTRELLA = (68, "estrella", "star", SciCategory.STRUCTURE)
    PLANETA = (69, "planeta", "planet", SciCategory.STRUCTURE)
    VIDA = (70, "vida", "life", SciCategory.STRUCTURE)
    NAVE = (71, "nave", "vessel", SciCategory.STRUCTURE)
    # -- constructos numéricos --------------------------------------------------
    NUMERO = (80, "número", "number", SciCategory.NUMBER)
    CONSTANTE = (81, "constante", "constant", SciCategory.NUMBER)
    UNIDAD = (82, "unidad", "unit", SciCategory.NUMBER)
    CERO = (83, "cero", "zero", SciCategory.NUMBER)
    INFINITO = (84, "infinito", "infinite", SciCategory.NUMBER)

    def __new__(cls, code: int, es: str, en: str, category: SciCategory):
        obj = object.__new__(cls)
        obj._value_ = code
        obj.code = code
        obj.es = es
        obj.en = en
        obj.category = category
        return obj

    @classmethod
    def by_code(cls, code: int) -> "SciPrimitive":
        return cls(code)

    @classmethod
    def lookup(cls, name: str) -> "SciPrimitive | None":
        return _SCI_BY_NAME.get(normalize_token(name))


_SCI_BY_NAME: dict[str, SciPrimitive] = {}
for _p in SciPrimitive:
    for _key in (_p.name, _p.es, _p.en):
        _SCI_BY_NAME[normalize_token(_key)] = _p

assert all(SCI_BASE <= p.code <= SCI_MAX for p in SciPrimitive), (
    "el plano científico no puede invadir el núcleo congelado ni el bit de derivados"
)


# -- dimensiones SI --------------------------------------------------------------

_DIM_NAMES = ("M", "L", "T", "K", "I", "N", "J")
_DIM_ATOMS = (
    SciPrimitive.MASA,
    SciPrimitive.LONGITUD,
    SciPrimitive.DURACION,
    SciPrimitive.TEMPERATURA,
    SciPrimitive.CARGA,
    SciPrimitive.CANTIDAD,
    SciPrimitive.LUMINOSIDAD,
)


@dataclass(frozen=True)
class Dimension:
    """Vector de exponentes SI: masa, longitud, tiempo, temperatura,
    corriente/carga, cantidad de sustancia, intensidad luminosa.

    Es la parte de una magnitud que **no** depende de la especie: dos
    civilizaciones sin unidades comunes comparten igualmente el hecho de
    que una velocidad es L·T⁻¹.
    """

    M: int = 0
    L: int = 0
    T: int = 0
    K: int = 0
    I: int = 0
    N: int = 0
    J: int = 0

    def as_tuple(self) -> tuple[int, ...]:
        return tuple(getattr(self, name) for name in _DIM_NAMES)

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(*(a + b for a, b in zip(self.as_tuple(), other.as_tuple())))

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(*(a - b for a, b in zip(self.as_tuple(), other.as_tuple())))

    def __pow__(self, n: int) -> "Dimension":
        return Dimension(*(a * n for a in self.as_tuple()))

    def is_dimensionless(self) -> bool:
        return not any(self.as_tuple())

    def atoms(self) -> tuple[SciPrimitive, ...]:
        """Los átomos de magnitud con exponente no nulo."""
        return tuple(
            atom for atom, exp in zip(_DIM_ATOMS, self.as_tuple()) if exp
        )

    def notation(self) -> str:
        """Notación legible: 'M·L²·T⁻²' (energía)."""
        superscripts = {"-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
                        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}
        parts = []
        for name, exp in zip(_DIM_NAMES, self.as_tuple()):
            if not exp:
                continue
            if exp == 1:
                parts.append(name)
            else:
                parts.append(name + "".join(superscripts[c] for c in str(exp)))
        return "·".join(parts) if parts else "1"

    def to_bytes(self) -> bytes:
        """7 bytes con signo: un exponente por dimensión (rango -128..127)."""
        return bytes((exp & 0xFF) for exp in self.as_tuple())

    @classmethod
    def from_bytes(cls, data: bytes) -> "Dimension":
        if len(data) < 7:
            raise ValueError("una dimensión ocupa 7 bytes")
        return cls(*(b - 256 if b > 127 else b for b in data[:7]))


# Dimensiones de referencia (no son unidades: son formas).
DIMENSIONLESS = Dimension()
MASS = Dimension(M=1)
LENGTH = Dimension(L=1)
TIME = Dimension(T=1)
TEMPERATURE = Dimension(K=1)
SPEED = Dimension(L=1, T=-1)
ACCELERATION = Dimension(L=1, T=-2)
FORCE = Dimension(M=1, L=1, T=-2)
ENERGY = Dimension(M=1, L=2, T=-2)
POWER = Dimension(M=1, L=2, T=-3)
FREQUENCY = Dimension(T=-1)
DENSITY = Dimension(M=1, L=-3)
PRESSURE = Dimension(M=1, L=-1, T=-2)


# -- cantidades físicas ------------------------------------------------------------

@dataclass(frozen=True)
class Quantity:
    """Cantidad física: mantisa entera × 10^exponente, con dimensión SI.

    La mantisa es un entero binario, no una cadena de dígitos: la
    codificación es independiente de la base numérica del emisor.
    """

    mantissa: int
    exponent: int = 0
    dimension: Dimension = DIMENSIONLESS

    @classmethod
    def of(cls, value: float, dimension: Dimension = DIMENSIONLESS, digits: int = 6) -> "Quantity":
        """Construye una cantidad desde un float, con `digits` cifras significativas."""
        if value == 0:
            return cls(0, 0, dimension)
        exponent = math.floor(math.log10(abs(value))) - (digits - 1)
        mantissa = round(value / (10 ** exponent))
        # normaliza los ceros finales para que la forma binaria sea mínima
        while mantissa and mantissa % 10 == 0:
            mantissa //= 10
            exponent += 1
        return cls(mantissa, exponent, dimension)

    @property
    def value(self) -> float:
        return self.mantissa * (10.0 ** self.exponent)

    def __mul__(self, other: "Quantity") -> "Quantity":
        return Quantity(
            self.mantissa * other.mantissa,
            self.exponent + other.exponent,
            self.dimension * other.dimension,
        )

    def __truediv__(self, other: "Quantity") -> "Quantity":
        if other.mantissa == 0:
            raise ZeroDivisionError("cantidad con mantisa nula")
        return Quantity.of(
            self.value / other.value, self.dimension / other.dimension
        )

    def compatible_with(self, other: "Quantity") -> bool:
        """Dos cantidades solo son comparables si comparten dimensión."""
        return self.dimension == other.dimension

    def compare(self, other: "Quantity") -> SciPrimitive:
        """Operador relacional resultante: IGUAL, MAYOR o MENOR.

        Lanza ValueError si las dimensiones no coinciden: comparar una
        masa con una longitud es un error de protocolo, no una opinión.
        """
        if not self.compatible_with(other):
            raise ValueError(
                f"dimensiones incompatibles: {self.dimension.notation()} vs "
                f"{other.dimension.notation()}"
            )
        if math.isclose(self.value, other.value, rel_tol=1e-9):
            return SciPrimitive.IGUAL
        return SciPrimitive.MAYOR if self.value > other.value else SciPrimitive.MENOR

    def notation(self) -> str:
        if self.dimension.is_dimensionless():
            return f"{self.value:g}"
        return f"{self.value:g} [{self.dimension.notation()}]"

    # -- serialización binaria --------------------------------------------------
    def to_bytes(self) -> bytes:
        """`signo+longitud | mantisa BE | exponente | dimensión (7 bytes)`."""
        magnitude = abs(self.mantissa)
        raw = magnitude.to_bytes(max(1, (magnitude.bit_length() + 7) // 8), "big")
        if len(raw) > 15:
            raise ValueError("mantisa demasiado grande para el marco v0.5")
        header = len(raw) | (0x80 if self.mantissa < 0 else 0)
        return bytes([header]) + raw + bytes([self.exponent & 0xFF]) + self.dimension.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["Quantity", int]:
        header = data[offset]
        length = header & 0x0F
        negative = bool(header & 0x80)
        offset += 1
        mantissa = int.from_bytes(data[offset : offset + length], "big")
        offset += length
        exponent = data[offset]
        exponent = exponent - 256 if exponent > 127 else exponent
        offset += 1
        dimension = Dimension.from_bytes(data[offset : offset + 7])
        return cls(-mantissa if negative else mantissa, exponent, dimension), offset + 7


# -- elementos químicos ---------------------------------------------------------------

# Máscaras humanas del número atómico. El protocolo transporta Z, nunca el nombre.
_ELEMENT_MASKS: dict[int, tuple[str, str, str]] = {
    1: ("H", "hidrógeno", "hydrogen"),
    2: ("He", "helio", "helium"),
    6: ("C", "carbono", "carbon"),
    7: ("N", "nitrógeno", "nitrogen"),
    8: ("O", "oxígeno", "oxygen"),
    10: ("Ne", "neón", "neon"),
    11: ("Na", "sodio", "sodium"),
    14: ("Si", "silicio", "silicon"),
    15: ("P", "fósforo", "phosphorus"),
    16: ("S", "azufre", "sulfur"),
    17: ("Cl", "cloro", "chlorine"),
    18: ("Ar", "argón", "argon"),
    20: ("Ca", "calcio", "calcium"),
    26: ("Fe", "hierro", "iron"),
    29: ("Cu", "cobre", "copper"),
    36: ("Kr", "kriptón", "krypton"),
    47: ("Ag", "plata", "silver"),
    54: ("Xe", "xenón", "xenon"),
    79: ("Au", "oro", "gold"),
    82: ("Pb", "plomo", "lead"),
    92: ("U", "uranio", "uranium"),
}

# Masas atómicas estándar (u) de los elementos con máscara conocida.
_ATOMIC_MASSES: dict[int, float] = {
    1: 1.008, 2: 4.0026, 6: 12.011, 7: 14.007, 8: 15.999, 10: 20.180,
    11: 22.990, 14: 28.085, 15: 30.974, 16: 32.06, 17: 35.45, 18: 39.95,
    20: 40.078, 26: 55.845, 29: 63.546, 36: 83.798, 47: 107.87, 54: 131.29,
    79: 196.97, 82: 207.2, 92: 238.03,
}

MAX_Z = 118


@dataclass(frozen=True)
class Element:
    """Un elemento **es** su número atómico. Todo lo demás es máscara.

    Z es universal: cualquier especie que haya hecho química cuenta los
    mismos protones. No hace falta compartir la palabra "carbono" para
    entenderse sobre Z=6.
    """

    Z: int

    def __post_init__(self) -> None:
        if not 1 <= self.Z <= MAX_Z:
            raise ValueError(f"número atómico fuera de rango: {self.Z}")

    @property
    def symbol(self) -> str:
        """Máscara humana del elemento; 'Z=113' si no la conocemos."""
        mask = _ELEMENT_MASKS.get(self.Z)
        return mask[0] if mask else f"Z={self.Z}"

    def name(self, lang: str = "es") -> str:
        mask = _ELEMENT_MASKS.get(self.Z)
        if not mask:
            return f"elemento {self.Z}" if lang == "es" else f"element {self.Z}"
        return mask[1] if lang == "es" else mask[2]

    def atomic_mass(self) -> Quantity | None:
        """Masa atómica estándar en unidades de masa atómica (adimensional
        respecto a SI: es un cociente de masas, universal por construcción)."""
        mass = _ATOMIC_MASSES.get(self.Z)
        return None if mass is None else Quantity.of(mass, DIMENSIONLESS)

    def to_bytes(self) -> bytes:
        return bytes([self.Z])

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["Element", int]:
        return cls(data[offset]), offset + 1

    @classmethod
    def lookup(cls, name: str) -> "Element | None":
        """Resuelve una máscara humana ('C', 'carbono', 'carbon') a su Z."""
        token = normalize_token(name).replace("=", "").replace(":", "")
        if token.startswith("z") and token[1:].isdigit():
            return cls(int(token[1:]))
        if token.isdigit():
            return cls(int(token))
        for z, mask in _ELEMENT_MASKS.items():
            if token in (normalize_token(m) for m in mask):
                return cls(z)
        return None


def resolve_science(name: str) -> SciPrimitive | Element | None:
    """Resuelve un nombre a átomo científico o elemento."""
    primitive = SciPrimitive.lookup(name)
    if primitive is not None:
        return primitive
    return Element.lookup(name)
