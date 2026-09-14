"""用 faster-whisper 對音檔做語音辨識，取得逐詞時間戳記。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Token


def _cache_key(audio_path: Path, model_size: str, language: str | None) -> str:
    stat = audio_path.stat()
    raw = f"{audio_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{model_size}|{language}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def default_cache_path(audio_path: Path, model_size: str, language: str | None) -> Path:
    key = _cache_key(audio_path, model_size, language)
    return audio_path.with_name(f"{audio_path.stem}.{key}.transcript.json")


def load_cached_tokens(cache_path: Path) -> list[Token] | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return [Token(text=t["text"], start=t["start"], end=t["end"]) for t in data]


def save_cached_tokens(cache_path: Path, tokens: list[Token]) -> None:
    data = [{"text": t.text, "start": t.start, "end": t.end} for t in tokens]
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def transcribe(
    audio_path: Path,
    model_size: str = "small",
    language: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[Token]:
    """對音檔做語音辨識，回傳帶時間戳記的詞列表。"""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "缺少 faster-whisper，請先執行：pip install faster-whisper"
        ) from exc

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language=language,
    )

    tokens: list[Token] = []
    for seg in segments:
        words = seg.words or []
        for w in words:
            text = w.word.strip()
            if not text:
                continue
            tokens.append(Token(text=text, start=w.start, end=w.end))
    return tokens


def transcribe_with_cache(
    audio_path: Path,
    model_size: str = "small",
    language: str | None = None,
    device: str = "cpu",
    compute_type: str = "int8",
    use_cache: bool = True,
    cache_path: Path | None = None,
) -> list[Token]:
    resolved_cache_path = cache_path or default_cache_path(audio_path, model_size, language)

    if use_cache:
        cached = load_cached_tokens(resolved_cache_path)
        if cached is not None:
            return cached

    tokens = transcribe(
        audio_path,
        model_size=model_size,
        language=language,
        device=device,
        compute_type=compute_type,
    )

    if use_cache:
        save_cached_tokens(resolved_cache_path, tokens)

    return tokens
