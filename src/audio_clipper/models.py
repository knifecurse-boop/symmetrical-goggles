"""共用的資料結構。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    """語音辨識結果中的一個詞／字，帶起訖時間（秒）。"""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Segment:
    """腳本中的一段要剪輯的片段。"""

    output_name: str
    text: str
    padding: float | None = None
    line_number: int = 0


@dataclass
class MatchResult:
    """某段腳本文字在音檔中比對到的位置。"""

    segment: Segment
    start: float
    end: float
    score: float
