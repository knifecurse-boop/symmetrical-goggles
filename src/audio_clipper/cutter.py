"""用 ffmpeg 剪下並匯出音檔片段。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FfmpegNotFoundError(RuntimeError):
    pass


def check_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise FfmpegNotFoundError(
            "找不到 ffmpeg，請先安裝（例如 apt install ffmpeg 或 brew install ffmpeg）"
        )
    if shutil.which("ffprobe") is None:
        raise FfmpegNotFoundError(
            "找不到 ffprobe，請先安裝 ffmpeg 套件（通常會一併附上 ffprobe）"
        )


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def cut_segment(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    if end <= start:
        raise ValueError(f"結束時間必須晚於開始時間：start={start}, end={end}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-vn",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
    ]
    if out_path.suffix.lower() == ".mp3":
        cmd += ["-q:a", "2"]
    cmd.append(str(out_path))

    subprocess.run(cmd, check=True, capture_output=True, text=True)
