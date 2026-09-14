"""把腳本片段的文字比對到語音辨識結果，找出對應的時間區間。"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from .models import MatchResult, Segment, Token


def _is_meaningful(ch: str) -> bool:
    # 忽略空白與標點符號，只保留文字／數字本身，讓腳本裡的換行、
    # 全形/半形標點差異不會影響比對結果。
    return ch.isalnum()


def _normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    """回傳去除空白標點後的字串，以及每個字元對應回原字串的索引。"""
    chars: list[str] = []
    mapping: list[int] = []
    for i, ch in enumerate(text):
        if _is_meaningful(ch):
            chars.append(ch)
            mapping.append(i)
    return "".join(chars), mapping


@dataclass
class _Transcript:
    """語音辨識結果的可搜尋索引。"""

    tokens: list[Token]
    normalized_text: str
    # normalized_text 的第 i 個字元，對應到 tokens 中第幾個 token
    norm_pos_to_token: list[int]


def build_transcript_index(tokens: list[Token]) -> _Transcript:
    if not tokens:
        raise ValueError("語音辨識結果是空的，無法比對任何片段")

    joined_parts: list[str] = []
    char_to_token: list[int] = []
    for token_idx, tok in enumerate(tokens):
        joined_parts.append(tok.text)
        char_to_token.extend([token_idx] * len(tok.text))
        joined_parts.append(" ")
        char_to_token.append(token_idx)
    joined_text = "".join(joined_parts)

    normalized_text, mapping = _normalize_with_mapping(joined_text)
    norm_pos_to_token = [char_to_token[orig_idx] for orig_idx in mapping]

    return _Transcript(
        tokens=tokens,
        normalized_text=normalized_text,
        norm_pos_to_token=norm_pos_to_token,
    )


def match_segment(transcript: _Transcript, segment: Segment) -> MatchResult:
    needle, _ = _normalize_with_mapping(segment.text)
    if not needle:
        raise ValueError(f"片段「{segment.output_name}」正規化後沒有可比對的文字")

    haystack = transcript.normalized_text
    alignment = fuzz.partial_ratio_alignment(needle, haystack)

    dest_start = alignment.dest_start
    dest_end = alignment.dest_end
    if dest_end <= dest_start:
        raise ValueError(f"片段「{segment.output_name}」在辨識結果中找不到對應位置")

    start_token_idx = transcript.norm_pos_to_token[dest_start]
    end_token_idx = transcript.norm_pos_to_token[dest_end - 1]

    start_time = transcript.tokens[start_token_idx].start
    end_time = transcript.tokens[end_token_idx].end

    return MatchResult(segment=segment, start=start_time, end=end_time, score=alignment.score)


def match_all(tokens: list[Token], segments: list[Segment]) -> list[MatchResult]:
    transcript = build_transcript_index(tokens)
    return [match_segment(transcript, seg) for seg in segments]
