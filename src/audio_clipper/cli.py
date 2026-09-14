"""命令列進入點：根據逐字稿腳本，批次剪輯並匯出音檔片段。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import asr, cutter
from .matcher import match_all
from .models import MatchResult
from .script_parser import ScriptParseError, parse_script

DEFAULT_MIN_SCORE = 70.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-clipper",
        description="根據逐字稿腳本，自動比對音檔位置並批次剪輯匯出多個片段。",
    )
    parser.add_argument("--audio", required=True, help="來源音檔路徑")
    parser.add_argument("--script", required=True, help="剪輯腳本路徑（見 README 說明格式）")
    parser.add_argument(
        "--output-dir", default="output", help="匯出片段的資料夾（預設：./output）"
    )
    parser.add_argument(
        "--language", default=None, help="音檔語言代碼，例如 zh / en；不指定則自動偵測"
    )
    parser.add_argument(
        "--model",
        default="small",
        help="faster-whisper 模型大小（tiny/base/small/medium/large-v3 等，預設 small）",
    )
    parser.add_argument("--device", default="cpu", help="推論裝置：cpu 或 cuda（預設 cpu）")
    parser.add_argument(
        "--compute-type", default="int8", help="faster-whisper compute_type（預設 int8）"
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.15,
        help="每段片段前後留白秒數，可被腳本裡個別段落的 padding 選項覆寫（預設 0.15）",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"比對信心分數（0-100）低於此值會顯示警告，建議人工複查（預設 {DEFAULT_MIN_SCORE}）",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只顯示比對到的時間區間，不實際剪輯匯出"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="不使用／不寫入語音辨識結果快取，強制重新辨識"
    )
    return parser


def _print_report(results: list[MatchResult], min_score: float) -> bool:
    all_ok = True
    name_width = max((len(r.segment.output_name) for r in results), default=10)
    print(f"{'輸出檔名':<{name_width}}  開始      結束      長度(s)  信心分數")
    for r in results:
        duration = r.end - r.start
        flag = ""
        if r.score < min_score:
            flag = "  ⚠ 建議人工複查"
            all_ok = False
        print(
            f"{r.segment.output_name:<{name_width}}  "
            f"{r.start:8.2f}  {r.end:8.2f}  {duration:7.2f}  {r.score:6.1f}{flag}"
        )
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    audio_path = Path(args.audio)
    script_path = Path(args.script)
    output_dir = Path(args.output_dir)

    if not audio_path.exists():
        print(f"錯誤：找不到音檔 {audio_path}", file=sys.stderr)
        return 1

    try:
        segments = parse_script(script_path)
    except (ScriptParseError, OSError) as exc:
        print(f"錯誤：腳本解析失敗：{exc}", file=sys.stderr)
        return 1

    try:
        cutter.check_ffmpeg_available()
    except cutter.FfmpegNotFoundError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    print(f"正在辨識音檔語音（模型：{args.model}，語言：{args.language or '自動偵測'}）...")
    try:
        tokens = asr.transcribe_with_cache(
            audio_path,
            model_size=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
            use_cache=not args.no_cache,
        )
    except RuntimeError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    if not tokens:
        print("錯誤：語音辨識沒有得到任何文字內容，請確認音檔內容或語言設定", file=sys.stderr)
        return 1

    try:
        results = match_all(tokens, segments)
    except ValueError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1

    duration = cutter.get_audio_duration(audio_path)
    for r in results:
        pad = r.segment.padding if r.segment.padding is not None else args.padding
        r.start = max(0.0, r.start - pad)
        r.end = min(duration, r.end + pad)

    print()
    all_ok = _print_report(results, args.min_score)
    print()

    if args.dry_run:
        print("（--dry-run 模式，未實際匯出檔案）")
        return 0 if all_ok else 2

    print(f"開始匯出到 {output_dir}/ ...")
    for r in results:
        out_path = output_dir / r.segment.output_name
        cutter.cut_segment(audio_path, r.start, r.end, out_path)
        print(f"  已匯出：{out_path}")

    print("完成。")
    if not all_ok:
        print(
            f"提醒：有片段的比對信心分數低於 {args.min_score}，"
            "已照樣匯出，但建議人工複查片段內容是否正確。"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
