"""Real speaker and microphone through PipeWire (`pw-play`, `pw-record`).

Mono, 16 kHz, s16. Nothing here decides anything: it turns samples into
air and air back into samples. `target` picks the capture node; the
monitor of the output sink is a digital loop that never leaves the PC,
the default source is the microphone and goes through the room.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
import wave
from typing import List, Optional, Sequence

from echo_wsp.link1.modem import RATE


def available() -> bool:
    return bool(shutil.which("pw-play") and shutil.which("pw-record"))


def write_wav(path: str, x: Sequence[int]) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(int(v).to_bytes(2, "little", signed=True) for v in x))


def read_wav(path: str) -> List[int]:
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("expected 16-bit samples")
        ch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    vals = [int.from_bytes(raw[i:i + 2], "little", signed=True)
            for i in range(0, len(raw), 2)]
    if ch == 1:
        return vals
    return [vals[i] for i in range(0, len(vals), ch)]  # first channel


def play(x: Sequence[int], volume: float = 0.6) -> None:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tx.wav")
        write_wav(p, x)
        subprocess.run(["pw-play", "--volume", str(volume), p], check=True)


def play_and_record(x: Sequence[int], *, target: Optional[str] = None,
                    capture_sink: bool = False,
                    volume: float = 0.6, pre_s: float = 0.6,
                    post_s: float = 0.8) -> List[int]:
    """Start recording, play x, keep recording a little, return samples."""
    with tempfile.TemporaryDirectory() as d:
        tx = os.path.join(d, "tx.wav")
        rx = os.path.join(d, "rx.wav")
        write_wav(tx, x)
        cmd = ["pw-record", "--rate", str(RATE), "--channels", "1",
               "--format", "s16"]
        if target:
            cmd += ["--target", target]
        if capture_sink:
            # Record what the sink plays (its monitor): a digital loop that
            # never reaches the air, and works even with the sink muted.
            cmd += ["-P", "{ stream.capture.sink = true }"]
        rec = subprocess.Popen(cmd + [rx], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        try:
            time.sleep(pre_s)
            subprocess.run(["pw-play", "--volume", str(volume), tx], check=True)
            time.sleep(post_s)
        finally:
            rec.send_signal(signal.SIGINT)
            try:
                rec.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rec.kill()
        return read_wav(rx)


def default_sink() -> Optional[str]:
    """node.name of the default sink, for a monitor capture."""
    try:
        out = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if "node.name" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    return None


def mixer_state() -> dict:
    """Volume and mute of the default sink and source, to restore later."""
    st = {}
    for dev in ("@DEFAULT_AUDIO_SINK@", "@DEFAULT_AUDIO_SOURCE@"):
        out = subprocess.run(["wpctl", "get-volume", dev], capture_output=True,
                             text=True).stdout.strip()
        parts = out.split()
        vol = parts[1] if len(parts) > 1 else "1.0"
        st[dev] = (vol, "[MUTED]" in out)
    return st


def set_mixer(state: dict) -> None:
    for dev, (vol, muted) in state.items():
        subprocess.run(["wpctl", "set-volume", dev, str(vol)], check=False)
        subprocess.run(["wpctl", "set-mute", dev, "1" if muted else "0"], check=False)


def record(seconds: float, *, target: Optional[str] = None) -> List[int]:
    with tempfile.TemporaryDirectory() as d:
        rx = os.path.join(d, "rx.wav")
        cmd = ["pw-record", "--rate", str(RATE), "--channels", "1",
               "--format", "s16"]
        if target:
            cmd += ["--target", target]
        rec = subprocess.Popen(cmd + [rx], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        try:
            time.sleep(seconds)
        finally:
            rec.send_signal(signal.SIGINT)
            rec.wait(timeout=5)
        return read_wav(rx)
