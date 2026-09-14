"""解析「剪輯腳本」檔案。

腳本格式範例：

    === 01_開場白.mp3 ===
    這是第一段要剪下來的逐字稿內容，
    可以跨多行書寫。

    === 02_重點整理.wav | padding=0.3 ===
    這是第二段的逐字稿內容...

每一段以 `=== 輸出檔名 ===` 開頭（輸出檔名的副檔名決定匯出的音檔格式），
標頭後面接的文字直到下一個標頭（或檔案結尾）為止都是該段的逐字稿內容。
標頭裡可以用 `|` 加上選項，目前支援 `padding=秒數`，用來覆寫該段前後
留白秒數（預設由命令列的 --padding 決定）。
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Segment

_HEADER_RE = re.compile(r"^===\s*(.+?)\s*===\s*$")


class ScriptParseError(ValueError):
    """腳本格式錯誤。"""


def parse_script(path: str | Path) -> list[Segment]:
    text = Path(path).read_text(encoding="utf-8")
    return parse_script_text(text)


def parse_script_text(text: str) -> list[Segment]:
    lines = text.splitlines()

    segments: list[Segment] = []
    current_header_line = 0
    current_name: str | None = None
    current_padding: float | None = None
    current_body: list[str] = []

    def flush() -> None:
        if current_name is None:
            return
        body = "\n".join(current_body).strip()
        if not body:
            raise ScriptParseError(
                f"第 {current_header_line} 行的段落「{current_name}」沒有任何逐字稿內容"
            )
        segments.append(
            Segment(
                output_name=current_name,
                text=body,
                padding=current_padding,
                line_number=current_header_line,
            )
        )

    for i, raw_line in enumerate(lines, start=1):
        m = _HEADER_RE.match(raw_line.strip())
        if m:
            flush()
            current_header_line = i
            current_body = []
            header = m.group(1)
            current_name, current_padding = _parse_header(header, i)
        else:
            if current_name is not None:
                current_body.append(raw_line)
            elif raw_line.strip():
                raise ScriptParseError(
                    f"第 {i} 行在任何 `=== 檔名 ===` 標頭之前出現了文字內容：{raw_line!r}"
                )

    flush()

    if not segments:
        raise ScriptParseError("腳本裡沒有找到任何 `=== 輸出檔名 ===` 段落")

    seen_names: dict[str, int] = {}
    for seg in segments:
        if seg.output_name in seen_names:
            raise ScriptParseError(
                f"輸出檔名重複：「{seg.output_name}」同時出現在第 "
                f"{seen_names[seg.output_name]} 行與第 {seg.line_number} 行"
            )
        seen_names[seg.output_name] = seg.line_number

    return segments


def _parse_header(header: str, line_number: int) -> tuple[str, float | None]:
    if "|" not in header:
        name = header.strip()
        padding = None
    else:
        name_part, opts_part = header.split("|", 1)
        name = name_part.strip()
        padding = None
        for opt in opts_part.split(","):
            opt = opt.strip()
            if not opt:
                continue
            if "=" not in opt:
                raise ScriptParseError(
                    f"第 {line_number} 行的選項格式錯誤：{opt!r}（應為 key=value）"
                )
            key, value = (part.strip() for part in opt.split("=", 1))
            if key == "padding":
                try:
                    padding = float(value)
                except ValueError as exc:
                    raise ScriptParseError(
                        f"第 {line_number} 行的 padding 值不是數字：{value!r}"
                    ) from exc
            else:
                raise ScriptParseError(f"第 {line_number} 行有不支援的選項：{key!r}")

    if not name:
        raise ScriptParseError(f"第 {line_number} 行沒有指定輸出檔名")
    if Path(name).suffix == "":
        raise ScriptParseError(
            f"第 {line_number} 行的輸出檔名「{name}」缺少副檔名（用副檔名決定匯出格式，例如 .mp3 / .wav）"
        )
    return name, padding
