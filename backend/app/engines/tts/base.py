"""TTS engine abstraction (engine-agnostic).

`EmotionIR` is the engine-independent intermediate representation of an
emotion/intensity, mapped from the parsed segment. Each engine declares its
`EngineCap`, and the synth service degrades gracefully for unsupported
parameters (docs: 情绪→参数 引擎无关中间表示 + 能力探测降级).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class EmotionIR:
    emotion: str            # neutral/excited/confused/sad/angry/...
    intensity: int          # 0-100
    speed: float = 1.0      # 0.5-2.0
    pitch: float = 0.0      # relative offset
    volume: float = 1.0     # 0-1.5
    style_tag: str = ""     # engine style label if supported


@dataclass
class EngineCap:
    speed: bool = True
    pitch: bool = True
    volume: bool = True
    style_tags: bool = False
    emotion_params: bool = False  # fine params like breath/tremor


@dataclass
class VoiceRef:
    voice_id: int
    name: str
    engine: str
    engine_voice_id: str
    timbre_hint: float = 0.0  # deterministic pitch offset for the stub


@runtime_checkable
class TTSEngine(Protocol):
    def capabilities(self) -> EngineCap: ...
    def synthesize(self, text: str, voice: VoiceRef, ir: EmotionIR) -> bytes:
        """Return WAV bytes for the given text."""
        ...
