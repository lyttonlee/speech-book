"""Stub TTS engine: synthesizes audible WAV tones (POC, no model needed).

Proves the engine abstraction + EmotionIR path end-to-end. Production swaps
`get_tts_engine()` for IndexTTSEngine / Qwen3TTSEngine (docs §5.5).
"""
from __future__ import annotations

import io
import math
import struct

from app.engines.tts.base import EmotionIR, EngineCap, VoiceRef

SAMPLE_RATE = 16000


def _build_wav(samples: list[float]) -> bytes:
    buf = io.BytesIO()
    n = len(samples)
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + n * 2))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", n * 2))
    for s in samples:
        v = max(-1.0, min(1.0, s))
        buf.write(struct.pack("<h", int(v * 32767)))
    return buf.getvalue()


def _read_samples(blob: bytes) -> list[int]:
    pos = 12
    data = b""
    while pos + 8 <= len(blob):
        cid = blob[pos : pos + 4]
        size = struct.unpack("<I", blob[pos + 4 : pos + 8])[0]
        if cid == b"data":
            data = blob[pos + 8 : pos + 8 + size]
            break
        pos += 8 + size
    return list(struct.unpack("<%dh" % (len(data) // 2), data))


class StubTTSEngine:
    def capabilities(self) -> EngineCap:
        return EngineCap(speed=True, pitch=True, volume=True, style_tags=False, emotion_params=False)

    def synthesize(self, text: str, voice: VoiceRef, ir: EmotionIR) -> bytes:
        base = 180.0 * (2 ** (voice.timbre_hint / 12.0))
        freq = base * (1.0 + ir.pitch)
        dur = min(8.0, max(0.4, len(text) * 0.07 / max(0.3, ir.speed)))
        amp = min(1.0, ir.volume) * 0.6
        nsamp = int(SAMPLE_RATE * dur)
        samples: list[float] = []
        for i in range(nsamp):
            t = i / SAMPLE_RATE
            s = math.sin(2 * math.pi * freq * t) * 0.7 + math.sin(2 * math.pi * freq * 2 * t) * 0.2
            env = math.sin(math.pi * i / nsamp)
            samples.append(s * amp * env)
        return _build_wav(samples)


def concatenate_wav(blobs: list[bytes]) -> bytes:
    merged: list[int] = []
    for b in blobs:
        if b:
            merged.extend(_read_samples(b))
    return _build_wav([s / 32767.0 for s in merged])


_engine: StubTTSEngine | None = None


def get_tts_engine() -> StubTTSEngine:
    global _engine
    if _engine is None:
        _engine = StubTTSEngine()
    return _engine
