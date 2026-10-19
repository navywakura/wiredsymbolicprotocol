"""Descubrimiento fonético (v0.5): el módulo Grace.

Todo lo anterior en WSP presupone un diccionario compartido. Este módulo
elimina esa presuposición: escucha audio de una fuente **desconocida**,
que no habla la retícula de WSP ni ninguna otra que conozcamos, y
construye el diccionario desde cero.

El método es el de Ryland Grace: escuchar, medir, agrupar lo que se
repite, y atar cada firma recurrente a un significado cuando el contexto
lo permite. Nada de traducir palabras: **medir espectros y correlacionar**.

    1. `observe`  — cada evento sonoro se mide y se describe como su
                    conjunto de parciales relativos a su propia raíz.
    2. `cluster`  — las descripciones que se repiten forman `Signature`s.
    3. `bind`     — una firma se ata a un átomo WSP, sea a mano o por
                    correlación con un contexto conocido (`align_and_bind`).
    4. `decode`   — con el mapa aprendido, el audio exótico se lee como
                    paquete simbólico.

Las firmas son **invariantes a la altura**: se describen por ratios
respecto a su propia raíz, así que un mismo símbolo emitido una octava
más abajo produce la misma firma. Sin esa invariancia no habría
diccionario posible con un emisor cuyo registro no controlamos.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from dataclasses import dataclass, field as dataclass_field

from .concepts import resolve
from .emotion import Emotion
from .grammar import Field, FieldTag, normalize
from .multiphonic import _chord_events, _goertzel, spectrum
from .primitives import Primitive
from .primitives_science import Element, SciPrimitive
from .symbol import Message, Symbol

# Resolución del fingerprint: dos parciales dentro de este margen son "el mismo".
CENTS_BUCKET = 30.0
_MIN_PARTIAL = 0.18      # magnitud mínima de un parcial, relativa al pico
_MAX_PARTIALS = 8
_F_LOW, _F_HIGH = 40.0, 5000.0


def cents(ratio: float) -> float:
    return 1200.0 * math.log2(ratio)


def _quantize_cents(ratio: float) -> int:
    return int(round(cents(ratio) / CENTS_BUCKET))


# -- observación -------------------------------------------------------------------

@dataclass(frozen=True)
class Observation:
    """Un evento sonoro medido: cuándo, a qué altura y con qué parciales."""

    at: float
    root_hz: float
    ratios: tuple[float, ...]
    magnitudes: tuple[float, ...]

    @property
    def fingerprint(self) -> tuple[int, ...]:
        """Descriptor invariante a la altura: ratios cuantizados en cents."""
        return tuple(sorted(_quantize_cents(r) for r in self.ratios))

    def notation(self) -> str:
        voices = " ".join(f"{r:.3f}" for r in self.ratios)
        return f"t={self.at:6.2f}s f0={self.root_hz:7.1f}Hz [{voices}]"


def _read_wav(path: str) -> tuple[list[float], int]:
    with wave.open(path, "rb") as f:
        if f.getsampwidth() != 2:
            raise ValueError("solo se soporta WAV PCM de 16 bits")
        sr, channels = f.getframerate(), f.getnchannels()
        raw = f.readframes(f.getnframes())
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    if channels > 1:
        values = values[::channels]
    return [v / 32768.0 for v in values], sr


def _peaks(chunk: list[float], sr: int) -> list[tuple[float, float]]:
    """Picos espectrales significativos: [(frecuencia, magnitud)]."""
    spec = [(f, m) for f, m in spectrum(chunk, sr) if _F_LOW <= f <= _F_HIGH]
    if not spec:
        return []
    ceiling = max(m for _, m in spec)
    if ceiling <= 1e-7:
        return []
    found: list[tuple[float, float]] = []
    for i in range(1, len(spec) - 1):
        freq, magnitude = spec[i]
        if magnitude < _MIN_PARTIAL * ceiling:
            continue
        if magnitude >= spec[i - 1][1] and magnitude >= spec[i + 1][1]:
            # interpolación parabólica para afinar la frecuencia del pico
            y0, y1, y2 = spec[i - 1][1], magnitude, spec[i + 1][1]
            denom = y0 - 2 * y1 + y2
            shift = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0
            step = spec[1][0] - spec[0][0]
            found.append((freq + shift * step, magnitude))
    found.sort(key=lambda p: -p[1])
    return sorted(found[:_MAX_PARTIALS], key=lambda p: p[0])


def observe(path: str) -> list[Observation]:
    """Mide cada evento sonoro del archivo como conjunto de parciales."""
    samples, sr = _read_wav(path)
    observations: list[Observation] = []
    for start, end in _chord_events(samples, sr):
        margin = int(0.02 * sr)
        chunk = samples[start + margin : max(start + margin + 1, end - margin)]
        peaks = _peaks(chunk, sr)
        if not peaks:
            continue
        root = peaks[0][0]
        observations.append(
            Observation(
                at=round(start / sr, 3),
                root_hz=root,
                ratios=tuple(f / root for f, _ in peaks),
                magnitudes=tuple(m / peaks[0][1] for _, m in peaks),
            )
        )
    return observations


# -- agrupamiento -------------------------------------------------------------------

@dataclass
class Signature:
    """Una firma acústica recurrente: candidata a "palabra" del emisor."""

    id: str
    fingerprint: tuple[int, ...]
    occurrences: int = 0
    times: list[float] = dataclass_field(default_factory=list)
    roots_hz: list[float] = dataclass_field(default_factory=list)
    mean_ratios: tuple[float, ...] = ()
    binding: str | None = None

    @property
    def register_hz(self) -> float:
        return sum(self.roots_hz) / len(self.roots_hz) if self.roots_hz else 0.0

    def notation(self) -> str:
        voices = " ".join(f"{r:.3f}" for r in self.mean_ratios)
        bound = self.binding or "—"
        return (
            f"{self.id:>8}  ×{self.occurrences:<3} f0≈{self.register_hz:6.1f}Hz "
            f"[{voices}]  → {bound}"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fingerprint": list(self.fingerprint),
            "occurrences": self.occurrences,
            "mean_ratios": [round(r, 5) for r in self.mean_ratios],
            "register_hz": round(self.register_hz, 2),
            "times": self.times[:32],
            "binding": self.binding,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Signature":
        signature = cls(
            id=data["id"],
            fingerprint=tuple(data.get("fingerprint", [])),
            occurrences=int(data.get("occurrences", 0)),
            times=list(data.get("times", [])),
            mean_ratios=tuple(data.get("mean_ratios", [])),
            binding=data.get("binding"),
        )
        register = data.get("register_hz")
        if register:
            signature.roots_hz = [float(register)]
        return signature


def cluster(observations: list[Observation], min_occurrences: int = 1) -> list[Signature]:
    """Agrupa observaciones por firma. Lo que se repite es vocabulario."""
    groups: dict[tuple[int, ...], list[Observation]] = {}
    for item in observations:
        groups.setdefault(item.fingerprint, []).append(item)

    signatures: list[Signature] = []
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for index, (fingerprint, members) in enumerate(ordered):
        if len(members) < min_occurrences:
            continue
        width = max(len(m.ratios) for m in members)
        mean_ratios = tuple(
            sum(m.ratios[i] for m in members if i < len(m.ratios))
            / max(1, sum(1 for m in members if i < len(m.ratios)))
            for i in range(width)
        )
        signatures.append(
            Signature(
                id=f"SIG-{index:02d}",
                fingerprint=fingerprint,
                occurrences=len(members),
                times=[m.at for m in members],
                roots_hz=[m.root_hz for m in members],
                mean_ratios=mean_ratios,
            )
        )
    return signatures


# -- mapa fonético ---------------------------------------------------------------------

@dataclass
class PhoneticMap:
    """Diccionario aprendido: firma acústica → átomo de WSP.

    Es el equivalente de la hoja de cálculo de Grace: no traduce
    palabras, ata espectros medidos a significados del protocolo.
    """

    speaker: str = "desconocido"
    signatures: dict[str, Signature] = dataclass_field(default_factory=dict)

    # -- construcción ---------------------------------------------------------
    def add(self, signature: Signature) -> Signature:
        existing = self.by_fingerprint(signature.fingerprint)
        if existing is not None:
            existing.occurrences += signature.occurrences
            existing.times.extend(signature.times)
            existing.roots_hz.extend(signature.roots_hz)
            return existing
        self.signatures[signature.id] = signature
        return signature

    @classmethod
    def from_observations(
        cls, observations: list[Observation], speaker: str = "desconocido"
    ) -> "PhoneticMap":
        phonetic = cls(speaker=speaker)
        for signature in cluster(observations):
            phonetic.signatures[signature.id] = signature
        return phonetic

    # -- consulta ----------------------------------------------------------------
    def by_fingerprint(self, fingerprint: tuple[int, ...]) -> Signature | None:
        for signature in self.signatures.values():
            if signature.fingerprint == fingerprint:
                return signature
        return None

    def match(self, observation: Observation) -> Signature | None:
        """Busca la firma de una observación, con tolerancia de un bucket."""
        exact = self.by_fingerprint(observation.fingerprint)
        if exact is not None:
            return exact
        target = observation.fingerprint
        for signature in self.signatures.values():
            if len(signature.fingerprint) != len(target):
                continue
            if all(abs(a - b) <= 1 for a, b in zip(signature.fingerprint, target)):
                return signature
        return None

    def unbound(self) -> list[Signature]:
        return [s for s in self.signatures.values() if s.binding is None]

    def bound(self) -> list[Signature]:
        return [s for s in self.signatures.values() if s.binding is not None]

    # -- aprendizaje ---------------------------------------------------------------
    def bind(self, signature_id: str, concept: str) -> Signature:
        """Ata una firma a un átomo de WSP (núcleo, plano científico o elemento)."""
        if signature_id not in self.signatures:
            raise KeyError(f"firma desconocida: {signature_id}")
        if _resolve_binding(concept) is None:
            raise ValueError(f"'{concept}' no es un átomo, concepto ni elemento de WSP")
        self.signatures[signature_id].binding = concept
        return self.signatures[signature_id]

    def align_and_bind(self, signature_ids: list[str], concepts: list[str]) -> int:
        """Ata por correlación posicional: el método de la piedra Rosetta.

        Si el emisor enuncia una serie cuyo significado conocemos —contar,
        nombrar elementos por su Z, señalar objetos— la alineación posicional
        ata cada firma a su átomo. Devuelve cuántas ataduras se hicieron.
        """
        bound = 0
        for signature_id, concept in zip(signature_ids, concepts):
            self.bind(signature_id, concept)
            bound += 1
        return bound

    def learn_from_sequence(
        self, observations: list[Observation], concepts: list[str]
    ) -> int:
        """Aprende de una emisión cuyo contenido conocemos, evento a evento."""
        if len(observations) != len(concepts):
            raise ValueError(
                f"la emisión tiene {len(observations)} eventos y el contexto "
                f"{len(concepts)} conceptos: la alineación sería una suposición"
            )
        bound = 0
        for observation, concept in zip(observations, concepts):
            signature = self.match(observation)
            if signature is None:
                signature = self.add(
                    Signature(
                        id=f"SIG-{len(self.signatures):02d}",
                        fingerprint=observation.fingerprint,
                        occurrences=1,
                        times=[observation.at],
                        roots_hz=[observation.root_hz],
                        mean_ratios=observation.ratios,
                    )
                )
            if signature.binding is None:
                self.bind(signature.id, concept)
                bound += 1
        return bound

    # -- persistencia ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "protocol": "echo-wsp",
            "artifact": "phonetic-map",
            "version": "0.5",
            "speaker": self.speaker,
            "cents_bucket": CENTS_BUCKET,
            "signatures": [s.to_dict() for s in self.signatures.values()],
        }

    def save(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "PhoneticMap":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        phonetic = cls(speaker=data.get("speaker", "desconocido"))
        for spec in data.get("signatures", []):
            signature = Signature.from_dict(spec)
            phonetic.signatures[signature.id] = signature
        return phonetic

    def report(self) -> str:
        lines = [
            f"hablante: {self.speaker}",
            f"firmas: {len(self.signatures)} "
            f"({len(self.bound())} atadas, {len(self.unbound())} sin atar)",
            "",
        ]
        lines += [
            s.notation()
            for s in sorted(self.signatures.values(), key=lambda s: -s.occurrences)
        ]
        return "\n".join(lines)


def _resolve_binding(concept: str):
    """Resuelve una atadura a átomo del núcleo, científico, elemento o derivado."""
    primitive = Primitive.lookup(concept)
    if primitive is not None:
        return primitive
    science = SciPrimitive.lookup(concept)
    if science is not None:
        return science
    element = Element.lookup(concept)
    if element is not None:
        return element
    try:
        return resolve(concept)
    except KeyError:
        return None


# -- decodificación con el mapa aprendido ---------------------------------------------

_SLOT_ORDER = (
    FieldTag.SOURCE, FieldTag.RELATION, FieldTag.TARGET, FieldTag.TIME, FieldTag.SPACE
)


def decode_with_map(path: str, phonetic: PhoneticMap) -> Message:
    """Audio exótico + diccionario aprendido → paquete simbólico.

    Sin etiquetas de campo en la señal (el emisor no habla nuestra
    gramática), los átomos se asignan a ranuras por su categoría: las
    entidades ocupan origen y destino, las relaciones la relación, y lo
    científico viaja en el plano de extensión. La certeza refleja qué
    fracción de la emisión supimos leer.
    """
    observations = observe(path)
    if not observations:
        return Message(packets=[])

    fields: list[Field] = []
    science: dict = {}
    understood = 0
    unknown: list[str] = []
    slots_used: set[FieldTag] = set()

    for observation in observations:
        signature = phonetic.match(observation)
        if signature is None or signature.binding is None:
            unknown.append(f"{observation.root_hz:.0f}Hz×{len(observation.ratios)}")
            continue
        understood += 1
        value = _resolve_binding(signature.binding)
        if isinstance(value, SciPrimitive):
            science.setdefault("atoms", []).append(value.name)
        elif isinstance(value, Element):
            science["element"] = value.Z
        else:
            tag = _slot_for(value, slots_used)
            if tag is not None:
                slots_used.add(tag)
                fields.append(Field(tag, value))

    symbol = normalize(fields)
    if science:
        symbol.meta.setdefault("science", {}).update(science)
    ratio = understood / len(observations)
    symbol.emotion = symbol.emotion.replace(certainty=round(2 * ratio - 1, 3))
    symbol.meta["discovery"] = {
        "speaker": phonetic.speaker,
        "events": len(observations),
        "understood": understood,
        "coverage": round(ratio, 3),
        "unknown": unknown[:16],
    }
    return Message(packets=[symbol])


def _slot_for(value, used: set[FieldTag]) -> FieldTag | None:
    """Asigna una ranura según la categoría del átomo, sin pisar las ocupadas."""
    from .primitives import Category

    category = getattr(value, "category", None)
    if category == Category.RELATION:
        preference = (FieldTag.RELATION, FieldTag.ACTION)
    elif category == Category.TIME:
        preference = (FieldTag.TIME,)
    elif category == Category.SPACE:
        preference = (FieldTag.SPACE,)
    else:
        preference = (FieldTag.SOURCE, FieldTag.TARGET)
    for tag in preference:
        if tag not in used:
            return tag
    return None


# -- emisión exótica (para pruebas y para responder al emisor) ----------------------------

def synthesize_signature(
    ratios: tuple[float, ...],
    root_hz: float,
    duration: float = 0.3,
    sr: int = 22050,
) -> list[float]:
    """Sintetiza una firma arbitraria: la voz del otro, no la retícula de WSP."""
    n = int(duration * sr)
    attack, release = 0.02, duration * 0.25
    amplitude = 0.8 / max(1, len(ratios))
    samples = []
    for i in range(n):
        t = i / sr
        if t < attack:
            env = t / attack
        elif t > duration - release:
            env = max(0.0, (duration - t) / release)
        else:
            env = 1.0
        samples.append(
            env * amplitude * sum(math.sin(2 * math.pi * root_hz * r * t) for r in ratios)
        )
    return samples


def write_exotic(
    utterance: list[tuple[tuple[float, ...], float]],
    path: str,
    sr: int = 22050,
    gap: float = 0.12,
) -> str:
    """Escribe una emisión exótica: lista de (ratios, raíz en Hz)."""
    samples: list[float] = []
    for ratios, root_hz in utterance:
        samples += synthesize_signature(ratios, root_hz, sr=sr)
        samples.extend(0.0 for _ in range(int(gap * sr)))
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
