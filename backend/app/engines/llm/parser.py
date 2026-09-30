"""Rule-based novel parser with an LLM enrichment hook (POC).

Production swaps `llm_enrich` for the real LLM adapter (docs §5.2), keeping
the same ParsedSegment contract so the rest of the pipeline is unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CHAPTER_RE = re.compile(
    r"^\s*第\s*([一二三四五六七八九十百千0-9]+)\s*章\b", re.MULTILINE
)


@dataclass
class ParsedSegment:
    type: str                 # narration | dialogue | psychology
    text: str
    speaker_name: str | None = None
    emotion: str = "neutral"
    intensity: int = 50
    confidence: float = 0.8


def split_chapters(text: str) -> list[tuple[str, str]]:
    """Return list of (title, body). Falls back to a single chapter."""
    matches = list(CHAPTER_RE.finditer(text))
    if len(matches) <= 1:
        return [("全文", text.strip())]
    chapters: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        title = m.group(0).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((title, text[start:end].strip()))
    return chapters


def _detect_speaker(before: str) -> str | None:
    # 说话人 = 引号前的名字；其后可跟「修饰副词 + 说/道类动词」
    # 例：张三低声说：→张三；张三说道：→张三；李四回答：→李四
    m = re.search(
        r"^\s*(?P<name>[一-鿿A-Za-z·]{1,8}?)\s*"
        r"(?P<adv>低声|轻声|大声|冷冷|缓缓|微微|轻轻|默默|忽然|突然|愤然|黯然|"
        r"无奈|温柔|平静|淡淡|静静|小声|柔声|厉声|高声|笑|哭|怒|叹|喜)?\s*"
        r"(?P<verb>说|道|说道|讲|回答|问道|喊道|叫道|嘟囔|嘀咕|答道)\s*[道：:：]?\s*$",
        before,
    )
    if m:
        return m.group("name")
    m2 = re.search(r"（([一-鿿A-Za-z·]{1,8})）\s*$", before)
    if m2:
        return m2.group(1)
    return None


def _emotion(text: str) -> tuple[str, int]:
    if "？！" in text or "?! " in text:
        return "angry", 85
    if "！" in text or "!" in text:
        return "excited", 75
    if "？" in text or "?" in text:
        return "confused", 60
    if "……" in text or "..." in text:
        return "sad", 65
    return "neutral", 50


def parse_paragraph(para: str) -> list[ParsedSegment]:
    para = para.strip()
    if not para:
        return []

    # 整段括号 → 心理描写
    if re.match(r"^[（(][\s\S]{1,200}[)）]$", para):
        emo, inten = _emotion(para)
        return [ParsedSegment("psychology", para, None, emo, inten, 0.8)]

    quotes = list(re.finditer(r"[“「\"]([^”」\"]*)[”」\"]", para))
    if not quotes:
        emo, inten = _emotion(para)
        return [ParsedSegment("narration", para, None, emo, inten, 0.85)]

    segs: list[ParsedSegment] = []
    cursor = 0
    for q in quotes:
        before = para[cursor : q.start()]
        spoken = q.group(1).strip()
        if before.strip():
            emo, inten = _emotion(before)
            segs.append(ParsedSegment("narration", before.strip(), None, emo, inten, 0.85))
        speaker = _detect_speaker(before)
        emo, inten = _emotion(spoken)
        conf = 0.78 if speaker else 0.6
        segs.append(ParsedSegment("dialogue", spoken, speaker, emo, inten, conf))
        cursor = q.end()
    tail = para[cursor:].strip()
    if tail:
        emo, inten = _emotion(tail)
        segs.append(ParsedSegment("narration", tail, None, emo, inten, 0.85))
    return segs


def llm_enrich(segments: list[ParsedSegment], context: str = "") -> list[ParsedSegment]:
    """LLM enrichment hook (POC: identity).

    Production: call the LLM adapter to refine speaker/emotion/intensity and
    fill cross-chapter consistency via the role dictionary.
    """
    return segments
