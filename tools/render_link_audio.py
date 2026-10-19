#!/usr/bin/env python3
"""Make the LINK modem recordings visible: a labelled spectrogram (PNG) and
a video with the sound and a scrolling spectrogram (MP4) per WAV in media/.

    python3 tools/render_link_audio.py [FONT.ttf|.woff]

Postcards are found by energy (the modem leaves silence between them) and
labelled from the transcript next to each WAV, in order; the count must
match. Every symbol of the zoomed postcard is read back from the spectrum
(strongest of the 16 data tones), independently of the modem's decoder.
Needs numpy, matplotlib, Pillow, fontTools and ffmpeg (libopenh264, aac).
"""
from __future__ import annotations

import json
import re
import subprocess
import textwrap
import tempfile
import wave
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from matplotlib import cm, font_manager, pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / 'media'
RATE, PERIOD, N = 16000, 640, 512
GREETING = (72, 81, 64, 32, 48)            # tone bins, 31.25 Hz each
DATA = tuple(36 + 4 * j for j in range(16))
NFFT, HOP = 512, 64                        # 250 columns per second
F_LO, F_HI = 700, 3300
PX_S = RATE // HOP

COLORS = {'veterano': '#000000', 'A → B': '#000000', 'honesto': '#000000',
          'novato': '#0000ee', 'forastero': '#d00000', 'mentiroso': '#d00000',
          'sybil-1': '#d00000', 'sybil-2': '#e07000', 'postal': '#000000'}

JOBS = [
    dict(wav='link1/link1-una-postal.wav', title='LINK-1 · una postal WSP por sonido',
         who=lambda line: 'postal', zoom=0),
    dict(wav='link1/link1-conversacion-mundo3.wav', title='LINK-1 · conversación, mundo 3',
         who=lambda line: 'veterano' if 'A→B' in line else 'novato', zoom=3),
    dict(wav='link2/link2-conversacion-firmada.wav', title='LINK-2 · firmada, con una postal falsa', zoom=7),
    dict(wav='link2/mentiroso-estrategico-conversacion.wav', title='El mentiroso estratégico', zoom=25),
    dict(wav='link3/link3-sybil.wav', title='LINK-3 · dos identidades falsas (Sybil)', zoom=43),
]


def font_file() -> str:
    """The rxlabs.org font (EchoPC, .woff) if given, else DejaVu Sans Mono."""
    import sys
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
        if src.suffix != '.woff':
            return str(src)
        out = Path(tempfile.gettempdir()) / (src.stem + '.ttf')
        f = TTFont(src)
        f.flavor = None
        f.save(out)
        return str(out)
    return font_manager.findfont('DejaVu Sans Mono')


def read_wav(p: Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float64)


def segments(x: np.ndarray) -> list:
    """Spans of sound separated by at least one period of silence."""
    on = np.abs(x) > 200
    idx = np.flatnonzero(on)
    spans, s, last = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - last > PERIOD:
            spans.append((int(s), int(last) + 1))
            s = i
        last = i
    spans.append((int(s), int(last) + 1))
    return spans


def labels(txt: Path, who=None) -> list:
    out = []
    for line in txt.read_text().splitlines():
        m = re.match(r'\s*(t\d+\s+)?(\S+(?: → \S+)?|[AB]→[AB])\s+([0-9a-f]{40,})\s+(.*)$', line)
        if not m:
            continue
        w = m.group(2).replace('→', ' → ').replace('  ', ' ') if '→' in m.group(2) else m.group(2)
        rest = m.group(4)
        status, _, text = rest.partition('·')
        if not text:
            status, text = ('', rest) if not rest.startswith(('RECHAZADA', 'firma')) else (rest, '')
        if status.startswith('RECHAZADA') and not text:
            text = 'la firma no cuadra con ninguna clave del grupo: se descarta sin leerla'
        out.append(dict(who=who(line) if who else w, status=status.strip(), text=text.strip(),
                        hex=m.group(3)))
    return out


def spectrogram(x: np.ndarray) -> np.ndarray:
    """dB in [0, 1] over [F_LO, F_HI], rows = low to high frequency."""
    pad = np.concatenate([np.zeros(NFFT // 2), x, np.zeros(NFFT)])
    cols = (len(x)) // HOP
    win = np.hanning(NFFT)
    frames = np.lib.stride_tricks.sliding_window_view(pad, NFFT)[::HOP][:cols] * win
    mag = np.abs(np.fft.rfft(frames, axis=1)).T
    lo, hi = int(F_LO * NFFT / RATE), int(F_HI * NFFT / RATE) + 1
    db = 20 * np.log10(mag[lo:hi] + 1e-3)
    top = np.percentile(db, 99.9)
    return np.clip((db - (top - 35)) / 35, 0, 1)


def read_symbols(x: np.ndarray, start: int, end: int) -> tuple:
    """Nibble carried by each data symbol, strongest of the 16 data tones."""
    pre = 10 * PERIOD
    n = (end - start - pre + PERIOD // 2) // PERIOD
    nib = []
    t = np.arange(N)
    for j in range(n):
        w = x[start + pre + j * PERIOD + 96: start + pre + j * PERIOD + 96 + N]
        p = [abs(np.dot(w, np.exp(-2j * np.pi * k * t / N))) for k in DATA]
        nib.append(int(np.argmax(p)))
    return pre, nib


def color(who: str) -> str:
    return COLORS.get(who, '#555555')


def png(job, x, segs, S, fp, out: Path):
    font_manager.fontManager.addfont(fp)
    fam = font_manager.FontProperties(fname=fp).get_name()
    plt.rcParams.update({'font.family': fam, 'font.size': 15, 'axes.edgecolor': '#000',
                         'axes.linewidth': 1})
    z = segs[job['zoom']]
    fig = plt.figure(figsize=(15.2, 9.6), dpi=100)
    gs = fig.add_gridspec(4, 1, height_ratios=[3.2, .45, 3.6, .9], hspace=.55)
    dur = len(x) / RATE
    gray = cm.gray_r
    # whole conversation
    ax = fig.add_subplot(gs[0])
    k = max(1, S.shape[1] // 1500)               # max-pool time so short tones survive the scale
    ov = S[:, :S.shape[1] // k * k].reshape(S.shape[0], -1, k).max(axis=2)
    ax.imshow(ov, origin='lower', aspect='auto', cmap=gray, extent=[0, dur, F_LO, F_HI], interpolation='nearest')
    ax.set_ylabel('Hz')
    ax.set_xlim(0, dur)
    ax.set_title(job['title'] + f' · {len(segs)} postales · {dur:.0f} s', loc='left', fontsize=18)
    ax.add_patch(Rectangle((z['start'] / RATE, F_LO), (z['end'] - z['start']) / RATE, F_HI - F_LO,
                           fill=False, ec='#0000ee', lw=2))
    ax.tick_params(labelbottom=False)
    band = fig.add_subplot(gs[1], sharex=ax)
    for i, s in enumerate(segs):
        bad = s['status'].startswith('RECHAZADA')
        band.add_patch(Rectangle((s['start'] / RATE, 0), (s['end'] - s['start']) / RATE, 1,
                                 color=color(s['who']), hatch='xx' if bad else None,
                                 fill=not bad, lw=1.5 if bad else 0))
    band.set_ylim(0, 1)
    band.set_yticks([])
    band.set_xlabel('segundos')
    seen = []
    for s in segs:
        if s['who'] not in seen:
            seen.append(s['who'])
    for k, w in enumerate(seen):
        band.text(1 - .14 * (len(seen) - k), 1.25, '■ ' + w, color=color(w), transform=band.transAxes,
                  fontsize=14, va='bottom')
    # one postcard, symbol by symbol
    pre, nib = read_symbols(x, z['start'], z['end'])
    a0, a1 = z['start'] // HOP, z['end'] // HOP + 1
    zx = fig.add_subplot(gs[2])
    span = (z['end'] - z['start']) / RATE
    zx.imshow(S[:, a0:a1], origin='lower', aspect='auto', cmap=gray, extent=[0, span, F_LO, F_HI],
              interpolation='nearest')
    zx.set_xlim(0, span)
    zx.set_ylabel('Hz')
    head = f"postal {job['zoom'] + 1}: {z['who']}" + (f" · {z['status']}" if z['status'] else '')
    zx.set_title(head, loc='left', fontsize=16, color=color(z['who']))
    for j, note in enumerate(GREETING):
        zx.axvline(j * 2 * PERIOD / RATE, color='#0000ee', lw=.6, alpha=.5)
    zx.axvline(pre / RATE, color='#0000ee', lw=1.5)
    zx.text(pre / RATE / 2, F_HI - 60, 'saludo\n5 notas', ha='center', va='top', color='#0000ee', fontsize=13)
    for j, v in enumerate(nib):
        t = (pre + j * PERIOD + PERIOD / 2) / RATE
        f = DATA[v] * RATE / N
        zx.text(t, f + 50, '0123456789abcdef'[v], ha='center', va='bottom', fontsize=10, color='#0000ee')
    zx.set_xlabel('segundos dentro de la postal')
    zx.set_yticks([1000, 2000, 3000])
    note = fig.add_subplot(gs[3])
    note.axis('off')
    note.text(0, .95, (z['text'] or '')[:120], fontsize=15, va='top')
    note.text(0, .25, f"{len(nib)} símbolos de 40 ms, cada uno un tono de 16 posibles entre "
              f"{DATA[0] * RATE // N} y {DATA[15] * RATE // N} Hz (4 bits). Las letras azules "
              f"son lo que se lee del espectro: 0 abajo, f arriba.", fontsize=13, va='top', color='#555')
    fig.savefig(out, dpi=100, bbox_inches='tight', pad_inches=.25, facecolor='white')
    plt.close(fig)


def video(job, x, segs, S, fp, out: Path):
    W, H, FPS = 1280, 720, 20
    big = ImageFont.truetype(fp, 34)
    mid = ImageFont.truetype(fp, 26)
    small = ImageFont.truetype(fp, 16)
    rgb = (255 * (1 - S[::-1])).astype(np.uint8)          # black = loud, white = silence
    SH = 330
    strip = Image.fromarray(rgb).resize((S.shape[1], SH), Image.NEAREST).convert('RGB')
    half = W // 2
    pad = Image.new('RGB', (strip.width + W, SH), 'white')
    pad.paste(strip, (half, 0))
    band = Image.new('RGB', (strip.width + W, 34), 'white')
    bd = ImageDraw.Draw(band)
    for i, s in enumerate(segs):
        a, b = half + s['start'] // HOP, half + s['end'] // HOP
        bad = s['status'].startswith('RECHAZADA')
        bd.rectangle([a, 2, b, 32], fill='white' if bad else color(s['who']), outline=color(s['who']), width=3)
        bd.text((a + 6, 7), f'{i + 1}', font=small, fill=color(s['who']) if bad else 'white')
    dur = len(x) / RATE
    ow = W - 80
    over = Image.new('RGB', (ow, 18), 'white')
    od = ImageDraw.Draw(over)
    for s in segs:
        od.rectangle([int(s['start'] / len(x) * ow), 0, int(s['end'] / len(x) * ow), 17], fill=color(s['who']))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-i', str(EV / job['wav']),
           '-c:v', 'libopenh264', '-b:v', '260k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '48k',
           '-shortest', '-movflags', '+faststart', str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(dur * FPS) + 1
    top = 110
    for f in range(frames):
        t = f / FPS
        col = int(t * PX_S)
        img = Image.new('RGB', (W, H), 'white')
        d = ImageDraw.Draw(img)
        d.text((40, 22), job['title'], font=mid, fill='black')
        d.text((W - 40, 22), f'{t:5.1f} / {dur:.0f} s', font=mid, fill='#555', anchor='ra')
        img.paste(over, (40, 66))
        mx = 40 + int(t / dur * ow)
        d.rectangle([mx - 2, 60, mx + 2, 90], fill='#0000ee')
        img.paste(pad.crop((col, 0, col + W, SH)), (0, top))
        img.paste(band.crop((col, 0, col + W, 34)), (0, top + SH + 6))
        d.line([half, top - 6, half, top + SH + 40], fill='#0000ee', width=3)
        for hz in (1000, 2000, 3000):
            y = top + SH - int((hz - F_LO) / (F_HI - F_LO) * SH)
            d.rectangle([W - 92, y - 11, W - 6, y + 11], fill='white')
            d.text((W - 12, y), f'{hz} Hz', font=small, fill='#0000ee', anchor='rm')
        n = int(t * RATE)
        cur = next((i for i, s in enumerate(segs) if s['start'] <= n < s['end'] + 2 * PERIOD), None)
        if cur is not None:
            s = segs[cur]
            sub = s['status'] if s['status'] and s['status'] != 'firma OK' else ''
            if s['status'] == 'firma OK':
                sub = 'firma OK'
            d.text((40, top + SH + 52), f"postal {cur + 1} · {s['who']}" + (f" · {sub}" if sub else ''),
                   font=big, fill=color(s['who']))
            for k, ln in enumerate(textwrap.wrap(s['text'], 72)[:2]):
                d.text((40, top + SH + 104 + 34 * k), ln, font=mid, fill='black')
        else:
            d.text((40, top + SH + 52), 'silencio' if n < segs[0]['start'] else '', font=big, fill='#555')
        # the bottom 70 px stay empty: browsers draw their controls there
        p.stdin.write(img.tobytes())
    p.stdin.close()
    assert p.wait() == 0


def main():
    fp = font_file()
    report = []
    for job in JOBS:
        wav = EV / job['wav']
        x = read_wav(wav)
        spans = segments(x)
        labs = labels(wav.with_suffix('.txt'), job.get('who')) if wav.with_suffix('.txt').exists() \
            else [dict(who='postal', status='', text='una postal de 16 bytes, saludo + símbolos', hex='')]
        assert len(spans) == len(labs), (job['wav'], len(spans), len(labs))
        segs = [dict(start=a, end=b, **l) for (a, b), l in zip(spans, labs)]
        S = spectrogram(x)
        stem = wav.with_suffix('')
        png(job, x, segs, S, fp, Path(f'{stem}-espectro.png'))
        video(job, x, segs, S, fp, Path(f'{stem}-espectro.mp4'))
        pre, nib = read_symbols(x, segs[job['zoom']]['start'], segs[job['zoom']]['end'])
        report.append(dict(wav=job['wav'], postcards=len(segs), seconds=round(len(x) / RATE, 1),
                           zoom=job['zoom'] + 1, symbols_read=''.join('0123456789abcdef'[v] for v in nib)))
        print(report[-1])
    (EV / 'espectros.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
