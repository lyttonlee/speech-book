"""Map a parsed segment's emotion+intensity to the engine-independent EmotionIR."""
from __future__ import annotations

from app.engines.tts.base import EmotionIR

# emotion -> base (speed, pitch, volume, style_tag)
_EMOTION_BASE = {
    "neutral": (1.0, 0.0, 1.0, ""),
    "excited": (1.25, 0.15, 1.1, "lively"),
    "confused": (0.9, -0.05, 0.95, "doubtful"),
    "sad": (0.8, -0.12, 0.85, "sorrow"),
    "angry": (1.15, 0.1, 1.15, "stern"),
    "fear": (0.85, -0.08, 0.9, "tense"),
    "happy": (1.2, 0.12, 1.05, "cheerful"),
}


def to_emotion_ir(emotion: str, intensity: int) -> EmotionIR:
    speed, pitch, volume, style = _EMOTION_BASE.get(
        emotion, _EMOTION_BASE["neutral"]
    )
    k = (intensity - 50) / 100.0  # -0.5 .. +0.5
    return EmotionIR(
        emotion=emotion,
        intensity=intensity,
        speed=round(max(0.5, min(2.0, speed + k * 0.3)), 3),
        pitch=round(pitch + k * 0.2, 3),
        volume=round(max(0.5, min(1.5, volume + k * 0.2)), 3),
        style_tag=style,
    )
