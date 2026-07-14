"""Transporte acústico reversible de paquete completo para WSP v0.4.1.

La máscara musical original permanece intacta. Al final del WAV se añade una
ráfaga FSK que transporta ``Message.to_bytes()`` con longitud y CRC32.
``listen_lossless`` recupera primero esa ráfaga y, si no existe o está dañada,
delega al decodificador heurístico anterior.
"""

from __future__ import annotations

import math
import struct
import tempfile
import wave
import zlib
from pathlib import Path

from .audio import BASE_FREQ, SAMPLE_RATE, render_wav as render_wav_legacy
from .listen import listen as listen_legacy
from .symbol import Message, Symbol

_FRAME_MAGIC = b"W41A"
_SEPARATOR_SECONDS = 0.30
_MARKER_SECONDS = 0.18
_MARKER_GAP_SECONDS = 0.06
_BIT_SECONDS = 0.018
_BIT_GAP_SECONDS = 0.004
_MARKER_HZ = 1980.0
_ZERO_HZ = 1320.0
_ONE_HZ = 1760.0
_AMPLITUDE = 0.48


def _tone(freq: float, seconds: float, sr: int, amplitude: float = _AMPLITUDE) -> list[int]:
    count = max(1, round(seconds * sr))
    attack = max(1, round(0.002 * sr))
    release = attack
    out: list[int] = []
    for index in range(count):
        envelope = 1.0
        if index < attack:
            envelope = index / attack
        elif index >= count - release:
            envelope = max(0.0, (count - index - 1) / release)
        value = math.sin(2.0 * math.pi * freq * index / sr)
        out.append(int(32767 * amplitude * envelope * value))
    return out


def _silence(seconds: float, sr: int) -> list[int]:
    return [0] * max(1, round(seconds * sr))


def _bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _frame(message: Message) -> bytes:
    payload = message.to_bytes()
    if len(payload) > 65535:
        raise ValueError("mensaje demasiado grande para el transporte acústico v0.4.1")
    header = _FRAME_MAGIC + struct.pack(">H", len(payload))
    crc = struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    return header + payload + crc


def _encode_trailer(message: Message, sr: int) -> list[int]:
    samples = _silence(_SEPARATOR_SECONDS, sr)
    samples += _tone(_MARKER_HZ, _MARKER_SECONDS, sr)
    samples += _silence(_MARKER_GAP_SECONDS, sr)
    for bit in _bits(_frame(message)):
        samples += _tone(_ONE_HZ if bit else _ZERO_HZ, _BIT_SECONDS, sr)
        samples += _silence(_BIT_GAP_SECONDS, sr)
    return samples


def _as_message(message: Message | Symbol) -> Message:
    return message if isinstance(message, Message) else Message(packets=[message])


def render_wav_lossless(
    message: Message | Symbol,
    path: str,
    base_freq: float = BASE_FREQ,
    sr: int = SAMPLE_RATE,
) -> str:
    """Renderiza la máscara musical y añade el paquete WSP completo como FSK."""
    msg = _as_message(message)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temporary = tmp.name
    try:
        render_wav_legacy(msg, temporary, base_freq=base_freq, sr=sr)
        with wave.open(temporary, "rb") as source:
            if source.getsampwidth() != 2 or source.getnchannels() != 1:
                raise ValueError("el renderizador base debe producir WAV mono PCM16")
            actual_sr = source.getframerate()
            raw = source.readframes(source.getnframes())
        musical = list(struct.unpack(f"<{len(raw) // 2}h", raw))
        combined = musical + _encode_trailer(msg, actual_sr)
        frames = struct.pack(f"<{len(combined)}h", *combined)
        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(actual_sr)
            output.writeframes(frames)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(target)


def _read_pcm16(path: str) -> tuple[list[float], int]:
    with wave.open(path, "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("solo se soporta WAV PCM de 16 bits")
        sr = source.getframerate()
        channels = source.getnchannels()
        raw = source.readframes(source.getnframes())
    values = struct.unpack(f"<{len(raw) // 2}h", raw)
    if channels > 1:
        values = values[::channels]
    return [value / 32768.0 for value in values], sr


def _goertzel(samples: list[float], sr: int, frequency: float) -> float:
    coefficient = 2.0 * math.cos(2.0 * math.pi * frequency / sr)
    previous = previous2 = 0.0
    for value in samples:
        current = value + coefficient * previous - previous2
        previous2, previous = previous, current
    return max(0.0, previous * previous + previous2 * previous2 - coefficient * previous * previous2)


def _find_last_long_silence(samples: list[float], sr: int) -> int | None:
    threshold = 0.002
    minimum = round(0.20 * sr)
    run_start: int | None = None
    candidate: int | None = None
    for index, value in enumerate(samples):
        if abs(value) <= threshold:
            if run_start is None:
                run_start = index
        elif run_start is not None:
            if index - run_start >= minimum:
                candidate = index
            run_start = None
    return candidate


def _decode_bit(chunk: list[float], sr: int) -> int:
    zero_energy = _goertzel(chunk, sr, _ZERO_HZ)
    one_energy = _goertzel(chunk, sr, _ONE_HZ)
    return int(one_energy > zero_energy)


def _decode_bytes(samples: list[float], sr: int, start: int, byte_count: int) -> bytes:
    tone_n = round(_BIT_SECONDS * sr)
    step = round((_BIT_SECONDS + _BIT_GAP_SECONDS) * sr)
    bits: list[int] = []
    for bit_index in range(byte_count * 8):
        position = start + bit_index * step
        chunk = samples[position:position + tone_n]
        if len(chunk) < tone_n:
            raise ValueError("tráiler acústico truncado")
        bits.append(_decode_bit(chunk, sr))
    output = bytearray()
    for offset in range(0, len(bits), 8):
        value = 0
        for bit in bits[offset:offset + 8]:
            value = (value << 1) | bit
        output.append(value)
    return bytes(output)


def decode_lossless(path: str) -> Message | None:
    """Recupera el paquete completo; devuelve ``None`` sin tráiler válido."""
    samples, sr = _read_pcm16(path)
    marker_start = _find_last_long_silence(samples, sr)
    if marker_start is None:
        return None

    marker_n = round(_MARKER_SECONDS * sr)
    marker = samples[marker_start:marker_start + marker_n]
    if len(marker) < marker_n:
        return None
    marker_energy = _goertzel(marker, sr, _MARKER_HZ)
    competing = max(_goertzel(marker, sr, _ZERO_HZ), _goertzel(marker, sr, _ONE_HZ))
    if marker_energy <= competing * 2.0:
        return None

    data_start = marker_start + marker_n + round(_MARKER_GAP_SECONDS * sr)
    try:
        header = _decode_bytes(samples, sr, data_start, 6)
        if header[:4] != _FRAME_MAGIC:
            return None
        payload_length = struct.unpack(">H", header[4:6])[0]
        full = _decode_bytes(samples, sr, data_start, 6 + payload_length + 4)
        payload = full[6:6 + payload_length]
        expected_crc = struct.unpack(">I", full[-4:])[0]
    except (ValueError, struct.error):
        return None

    if zlib.crc32(payload) & 0xFFFFFFFF != expected_crc:
        return None
    try:
        return Message.from_bytes(payload)
    except (ValueError, IndexError, struct.error, UnicodeDecodeError):
        return None


def listen_lossless(path: str) -> Message:
    """Decodifica v0.4.1 exactamente y conserva compatibilidad hacia atrás."""
    exact = decode_lossless(path)
    return exact if exact is not None else listen_legacy(path)
