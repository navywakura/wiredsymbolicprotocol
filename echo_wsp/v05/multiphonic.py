"""Capa M polifónica (v0.5): acordes simultáneos como unidad de significado.

Hasta la v0.4 la máscara sonora era una **melodía**: los ratios se
suceden en el tiempo y el significado se lee en la secuencia. Un emisor
con un órgano vocal capaz de varias voces simultáneas —el caso Rocky—
no habla en melodía: habla en **acordes**. Un solo acorde transporta un
campo completo del paquete.

Retícula de un acorde (ratios sobre la raíz f₀ del propio acorde):

    slot  ratio   función
      0    1/1    raíz / portadora (siempre presente, define f₀)
      1    9/8    etiqueta bit 0
      2    5/4    etiqueta bit 1
      3    3/2    etiqueta bit 2
      4   15/8    etiqueta bit 3
      5    9/4    carga bit 0
      6    5/2    carga bit 1
      7    3/1    carga bit 2
      8   15/4    carga bit 3
      9    9/2    carga bit 4
     10    5/1    paridad par sobre los 9 bits de datos

Es decir: **etiqueta (4 bits) + carga (5 bits) + paridad, todo sonando a
la vez**. La etiqueta es la de `grammar.FieldTag`, así que el acorde es
autodescriptivo y el orden de los acordes no altera el significado: la
polifonía y la sintaxis agnóstica son la misma idea en dos planos.

Como todo en WSP, la retícula es de **ratios**: f₀ puede ser cualquier
frecuencia. Un eridiano con una laringe a 400 Hz y un humano silbando a
180 Hz emiten el mismo símbolo.

Cargas mayores de 5 bits (átomos científicos, Z de un elemento,
cantidades físicas) se reparten en acordes de continuación `CONT`.
Un concepto derivado viaja como su composición: el nombre es máscara,
los átomos son el concepto.
"""

from __future__ import annotations

import cmath
import math
import struct
import wave
from dataclasses import dataclass, field as dataclass_field

from .concepts import Concept, Derived, define, registry
from .emotion import AXES, Emotion
from .grammar import Field, FieldTag, fields_of, normalize
from .primitives import Primitive
from .primitives_science import Element, Quantity, SciPrimitive, SCI_BASE
from .symbol import Message, Symbol

P = Primitive

# Retícula de la v0.5: raíz, 4 bits de etiqueta, 5 de carga, 1 de paridad.
ROOT_RATIO = 1.0
TAG_RATIOS: tuple[float, ...] = (9 / 8, 5 / 4, 3 / 2, 15 / 8)
PAYLOAD_RATIOS: tuple[float, ...] = (9 / 4, 5 / 2, 3.0, 15 / 4, 9 / 2)
PARITY_RATIO = 5.0
LATTICE: tuple[float, ...] = (ROOT_RATIO,) + TAG_RATIOS + PAYLOAD_RATIOS + (PARITY_RATIO,)

SAMPLE_RATE = 22050
BASE_FREQ = 180.0
CHORD_DURATION = 0.26
CHORD_GAP = 0.07
PACKET_GAP = 0.55

_PRESENCE_THRESHOLD = 0.40   # magnitud mínima de un parcial, relativa a la raíz
_F0_MIN, _F0_MAX = 60.0, 600.0


# -- el acorde como dato ---------------------------------------------------------

@dataclass(frozen=True)
class Chord:
    """Un campo etiquetado listo para sonar: etiqueta + carga de 5 bits."""

    tag: FieldTag
    payload: int

    def __post_init__(self) -> None:
        if not 0 <= self.payload <= 31:
            raise ValueError(f"carga fuera de 5 bits: {self.payload}")

    @property
    def parity(self) -> int:
        """Paridad par sobre los 9 bits de datos."""
        return (bin(int(self.tag)).count("1") + bin(self.payload).count("1")) & 1

    def ratios(self) -> tuple[float, ...]:
        """Los ratios que suenan simultáneamente en este acorde."""
        active = [ROOT_RATIO]
        for bit, ratio in enumerate(TAG_RATIOS):
            if int(self.tag) & (1 << bit):
                active.append(ratio)
        for bit, ratio in enumerate(PAYLOAD_RATIOS):
            if self.payload & (1 << bit):
                active.append(ratio)
        if self.parity:
            active.append(PARITY_RATIO)
        return tuple(active)

    def notation(self) -> str:
        fractions = {
            1.0: "1/1", 9 / 8: "9/8", 5 / 4: "5/4", 3 / 2: "3/2", 15 / 8: "15/8",
            9 / 4: "9/4", 5 / 2: "5/2", 3.0: "3/1", 15 / 4: "15/4", 9 / 2: "9/2",
            5.0: "5/1",
        }
        voices = " ".join(fractions[r] for r in self.ratios())
        return f"[{self.tag.name}:{self.payload:02d}] {voices}"


# -- campos → acordes ------------------------------------------------------------

def _concept_chords(tag: FieldTag, concept: Concept) -> list[Chord]:
    """Un primitivo es un acorde; un derivado es su composición encadenada."""
    if isinstance(concept, Primitive):
        return [Chord(tag, concept.code)]
    atoms = concept.components
    if not atoms:
        raise ValueError(f"concepto derivado sin componentes: {concept}")
    return [Chord(tag, atoms[0].code)] + [Chord(FieldTag.CONT, a.code) for a in atoms[1:]]


def _chunks_5bit(data: bytes) -> list[int]:
    """Trocea bytes en grupos de 5 bits (big-endian, relleno con ceros)."""
    bits = "".join(f"{b:08b}" for b in data)
    bits += "0" * ((-len(bits)) % 5)
    return [int(bits[i : i + 5], 2) for i in range(0, len(bits), 5)]


def _bytes_from_chunks(chunks: list[int], length: int) -> bytes:
    bits = "".join(f"{c:05b}" for c in chunks)
    return bytes(int(bits[i : i + 8], 2) for i in range(0, length * 8, 8))


def field_to_chords(item: Field) -> list[Chord]:
    """Traduce un campo etiquetado a la secuencia mínima de acordes."""
    tag = item.tag
    if tag.slot:
        return _concept_chords(tag, item.value)
    if tag.axis:
        level = max(0, min(31, int(round(float(item.value) * 15)) + 15))
        return [Chord(tag, level)]
    if tag is FieldTag.SCI:
        offset = item.value.code - SCI_BASE
        return [Chord(tag, offset >> 5), Chord(FieldTag.CONT, offset & 31)]
    if tag is FieldTag.ELEMENT:
        z = item.value.Z
        return [Chord(tag, z >> 5), Chord(FieldTag.CONT, z & 31)]
    if tag is FieldTag.QUANTITY:
        raw = item.value.to_bytes()
        chunks = _chunks_5bit(raw)
        return [Chord(tag, len(raw))] + [Chord(FieldTag.CONT, c) for c in chunks]
    raise ValueError(f"etiqueta sin representación polifónica: {tag!r}")


def symbol_to_chords(symbol: Symbol, order: list[FieldTag] | None = None) -> list[Chord]:
    """Todo el paquete como secuencia de acordes autodescriptivos."""
    from .grammar import sort_fields

    fields = fields_of(symbol)
    if order:
        fields = sort_fields(fields, order)
    chords: list[Chord] = []
    for item in fields:
        chords.extend(field_to_chords(item))
    return chords


# -- acordes → campos -------------------------------------------------------------

def _match_derived(atoms: list[Primitive]) -> Concept:
    """Un derivado se reconoce por su composición, no por su nombre."""
    if len(atoms) == 1:
        return atoms[0]
    wanted = tuple(atoms)
    for concept in registry().values():
        if concept.components == wanted:
            return concept
    # composición desconocida: el receptor la aprende (generatividad por el cable)
    name = "X_" + "_".join(a.name for a in atoms)
    return define(name, list(atoms))


def chords_to_fields(chords: list[Chord]) -> list[Field]:
    """Recompone los campos, resolviendo continuaciones."""
    fields: list[Field] = []
    index = 0
    while index < len(chords):
        chord = chords[index]
        tag = chord.tag
        index += 1
        if tag is FieldTag.CONT:
            continue  # continuación huérfana: se ignora
        continuations: list[int] = []
        while index < len(chords) and chords[index].tag is FieldTag.CONT:
            continuations.append(chords[index].payload)
            index += 1

        if tag.slot:
            atoms = [Primitive.by_code(chord.payload)]
            atoms += [Primitive.by_code(p) for p in continuations]
            fields.append(Field(tag, _match_derived(atoms)))
        elif tag.axis:
            fields.append(Field(tag, (chord.payload - 15) / 15.0))
        elif tag is FieldTag.SCI and continuations:
            code = SCI_BASE + (chord.payload << 5) + continuations[0]
            fields.append(Field(tag, SciPrimitive.by_code(code)))
        elif tag is FieldTag.ELEMENT and continuations:
            fields.append(Field(tag, Element((chord.payload << 5) + continuations[0])))
        elif tag is FieldTag.QUANTITY and continuations:
            raw = _bytes_from_chunks(continuations, chord.payload)
            quantity, _ = Quantity.from_bytes(raw)
            fields.append(Field(tag, quantity))
    return fields


# -- síntesis ----------------------------------------------------------------------

def synthesize_chords(
    chords: list[Chord],
    base: float = BASE_FREQ,
    sr: int = SAMPLE_RATE,
    duration: float = CHORD_DURATION,
    gap: float = CHORD_GAP,
) -> list[float]:
    """Sintetiza los acordes: todas las voces de un acorde suenan a la vez."""
    samples: list[float] = []
    attack = 0.018
    for chord in chords:
        ratios = chord.ratios()
        amplitude = 0.8 / max(1, len(ratios))
        n = int(duration * sr)
        release = duration * 0.22
        for i in range(n):
            t = i / sr
            if t < attack:
                env = t / attack
            elif t > duration - release:
                env = max(0.0, (duration - t) / release)
            else:
                env = 1.0
            samples.append(
                env * amplitude * sum(math.sin(2 * math.pi * base * r * t) for r in ratios)
            )
        samples.extend(0.0 for _ in range(int(gap * sr)))
    return samples


def render_wav(
    message: Message | Symbol,
    path: str,
    base: float = BASE_FREQ,
    sr: int = SAMPLE_RATE,
    order: list[FieldTag] | None = None,
) -> str:
    """Escribe el mensaje como WAV polifónico (un acorde por campo)."""
    packets = message.packets if isinstance(message, Message) else [message]
    samples: list[float] = []
    for index, packet in enumerate(packets):
        if index:
            samples.extend(0.0 for _ in range(int(PACKET_GAP * sr)))
        samples += synthesize_chords(symbol_to_chords(packet, order), base=base, sr=sr)
    peak = max((abs(s) for s in samples), default=1.0)
    if peak > 0.9:
        samples = [s * 0.9 / peak for s in samples]
    frames = b"".join(struct.pack("<h", int(s * 32767)) for s in samples)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(frames)
    return path


# -- análisis espectral -------------------------------------------------------------

def _fft(values: list[complex]) -> list[complex]:
    """FFT radix-2 iterativa (stdlib pura). `values` se rellena a potencia de 2."""
    n = 1 << (len(values) - 1).bit_length()
    data = list(values) + [0j] * (n - len(values))
    # permutación bit-reversa
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            data[i], data[j] = data[j], data[i]
    length = 2
    while length <= n:
        step = cmath.exp(-2j * math.pi / length)
        for start in range(0, n, length):
            w = 1 + 0j
            for k in range(start, start + length // 2):
                u = data[k]
                v = data[k + length // 2] * w
                data[k] = u + v
                data[k + length // 2] = u - v
                w *= step
        length <<= 1
    return data


def spectrum(samples: list[float], sr: int) -> list[tuple[float, float]]:
    """Espectro de magnitud con ventana de Hann: [(frecuencia, magnitud)]."""
    n = len(samples)
    if n < 8:
        return []
    windowed = [
        s * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, s in enumerate(samples)
    ]
    bins = _fft([complex(v) for v in windowed])
    size = len(bins)
    return [(i * sr / size, abs(bins[i]) * 2 / n) for i in range(size // 2)]


def _goertzel(samples: list[float], sr: int, freq: float) -> float:
    """Magnitud a una frecuencia concreta (más barato que un espectro completo)."""
    w = 2 * math.pi * freq / sr
    coeff = 2 * math.cos(w)
    s1 = s2 = 0.0
    for v in samples:
        s0 = v + coeff * s1 - s2
        s2, s1 = s1, s0
    power = s1 * s1 + s2 * s2 - coeff * s1 * s2
    return math.sqrt(max(0.0, power)) * 2 / max(1, len(samples))


def _chord_events(samples: list[float], sr: int) -> list[tuple[int, int]]:
    """Segmenta la señal en eventos sonoros (inicio, fin) por envolvente."""
    hop = max(1, sr // 400)
    win = hop * 4
    envelope = [
        math.sqrt(sum(v * v for v in samples[i : i + win]) / max(1, len(samples[i : i + win])))
        for i in range(0, max(1, len(samples) - win), hop)
    ]
    if not envelope:
        return []
    threshold = max(envelope) * 0.12
    events: list[tuple[int, int]] = []
    start = None
    for i, value in enumerate(envelope):
        if value >= threshold and start is None:
            start = i
        elif value < threshold and start is not None:
            if (i - start) * hop >= 0.05 * sr:
                events.append((start * hop, i * hop))
            start = None
    if start is not None and (len(envelope) - start) * hop >= 0.05 * sr:
        events.append((start * hop, len(samples)))
    return events


def _estimate_root(chunk: list[float], sr: int) -> float | None:
    """Estima f₀ como el parcial más grave, refinado por ajuste de retícula.

    La raíz 1:1 siempre suena, así que es el pico significativo más bajo.
    Se refina eligiendo el candidato que maximiza la energía explicada por
    la retícula: eso descarta engancharse a un submúltiplo.
    """
    spec = spectrum(chunk, sr)
    if not spec:
        return None
    band = [(f, m) for f, m in spec if _F0_MIN * 0.8 <= f <= _F0_MAX * 1.2]
    if not band:
        return None
    ceiling = max(m for _, m in band)
    peaks = [
        (f, m)
        for i, (f, m) in enumerate(band)
        if m >= 0.25 * ceiling
        and (i == 0 or band[i - 1][1] <= m)
        and (i + 1 >= len(band) or band[i + 1][1] <= m)
    ]
    if not peaks:
        return None

    def lattice_score(f0: float) -> float:
        if not _F0_MIN <= f0 <= _F0_MAX:
            return 0.0
        root = _goertzel(chunk, sr, f0)
        if root <= 1e-6:
            return 0.0
        inside = sum(_goertzel(chunk, sr, f0 * r) for r in LATTICE)
        total = sum(m for _, m in spec) + 1e-9
        return inside / total

    candidates = [f for f, _ in peaks[:4]]
    best = max(candidates, key=lattice_score)
    # refinado fino alrededor del mejor candidato
    step = best * 0.004
    for _ in range(6):
        neighbours = [best - step, best, best + step]
        best = max(neighbours, key=lattice_score)
        step /= 2
    return best


def decode_chord(chunk: list[float], sr: int) -> tuple[Chord | None, dict]:
    """Lee un acorde: presencia de cada parcial de la retícula sobre su raíz."""
    root_freq = _estimate_root(chunk, sr)
    if root_freq is None:
        return None, {"reason": "sin raíz detectable"}
    magnitudes = [_goertzel(chunk, sr, root_freq * r) for r in LATTICE]
    root_magnitude = magnitudes[0]
    if root_magnitude <= 1e-6:
        return None, {"reason": "raíz sin energía", "base_hz": round(root_freq, 2)}
    present = [m >= _PRESENCE_THRESHOLD * root_magnitude for m in magnitudes]

    tag_bits = sum(1 << i for i in range(4) if present[1 + i])
    payload = sum(1 << i for i in range(5) if present[5 + i])
    parity_heard = present[10]
    chord = Chord(FieldTag(tag_bits), payload)
    meta = {
        "base_hz": round(root_freq, 2),
        "parity_ok": parity_heard == bool(chord.parity),
        "voices": len(chord.ratios()),
    }
    return chord, meta


def read_chords(path: str) -> tuple[list[Chord], list[dict]]:
    """Lee un WAV polifónico y devuelve sus acordes con diagnóstico."""
    with wave.open(path, "rb") as f:
        if f.getsampwidth() != 2:
            raise ValueError("solo se soporta WAV PCM de 16 bits")
        sr = f.getframerate()
        channels = f.getnchannels()
        raw = f.readframes(f.getnframes())
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    if channels > 1:
        values = values[::channels]
    samples = [v / 32768.0 for v in values]

    chords: list[Chord] = []
    diagnostics: list[dict] = []
    for start, end in _chord_events(samples, sr):
        margin = int(0.02 * sr)
        chord, meta = decode_chord(samples[start + margin : end - margin], sr)
        meta["at"] = round(start / sr, 3)
        if chord is not None:
            chords.append(chord)
        diagnostics.append(meta)
    return chords, diagnostics


def listen_chords(path: str) -> Message:
    """WAV polifónico → mensaje simbólico.

    Los fallos de paridad no descartan el paquete: rebajan el eje de
    certeza. La duda es parte del protocolo, no un error fatal.
    """
    chords, diagnostics = read_chords(path)
    if not chords:
        return Message(packets=[])

    fields = chords_to_fields(chords)
    symbol = normalize(fields)
    bad_parity = sum(1 for d in diagnostics if d.get("parity_ok") is False)
    if bad_parity:
        penalty = min(1.0, bad_parity / max(1, len(chords)))
        symbol.emotion = symbol.emotion.replace(
            certainty=symbol.emotion.certainty * (1 - penalty) - penalty
        )
    symbol.meta["polyphonic"] = {
        "chords": len(chords),
        "parity_errors": bad_parity,
        "base_hz": diagnostics[0].get("base_hz") if diagnostics else None,
    }
    return Message(packets=[symbol])
