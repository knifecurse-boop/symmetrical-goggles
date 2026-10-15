"""命令列進入點：瀏覽教材庫、依出題設定檔產生試卷、或啟動網頁介面。"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from .generator import DEFAULT_EFFORT, DEFAULT_MODEL, ExamGenerator, GenerationError, build_material, build_section_request
from .library import Library, LibraryError
from .models import ExamSpec
from .question_types import QUESTION_TYPES, get_type
from .render import write_all

DEFAULT_LIBRARY = "library"


def load_spec(path: Path) -> ExamSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ExamSpec.model_validate(data)


def cmd_catalog(args) -> int:
    lib = Library(args.library)
    for mag in lib.catalog():
        print(f"{mag['name']}  [{mag['id']}]  {mag['level']}")
        for issue in mag["issues"]:
            print(f"  {issue['id']}  {issue['title']}")
            for u in issue["units"]:
                print(f"    {u['id']}  {u['title']}（{u['topic']}）單字 {u['vocab_count']} 個")
                if u["grammar"]:
                    print(f"        文法：{'、'.join(u['grammar'])}")
                if u["patterns"]:
                    print(f"        句型：{'、'.join(u['patterns'])}")
    print("\n可用題型：")
    for qt in QUESTION_TYPES.values():
        print(f"  {qt.key:<22}{qt.name}")
    return 0


def cmd_generate(args) -> int:
    lib = Library(args.library)
    spec = load_spec(Path(args.spec))

    if args.dry_run:
        units = lib.resolve_spec(spec)
        for s in spec.sections:
            qt = get_type(s.type)
            print(f"===== {qt.name} =====")
            print(build_material(units, s.focus or spec.focus))
            print("-----")
            print(build_section_request(spec, s, qt, used_targets=[]))
            print()
        return 0

    gen = ExamGenerator(lib, model=args.model, effort=args.effort, on_progress=lambda m: print(m, file=sys.stderr))
    exam = gen.generate(spec)
    stem = args.name or re.sub(r"[\\/:*?\"<>|\s]+", "_", spec.title) + datetime.now().strftime("_%Y%m%d_%H%M")
    for p in write_all(exam, args.out, stem):
        print(p)
    return 0


def cmd_web(args) -> int:
    from .web import create_app

    app = create_app(args.library, model=args.model, effort=args.effort, output_dir=args.out)
    print(f"開啟瀏覽器前往 http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exam-gen", description="英文試卷 AI 生成器")
    parser.add_argument("--library", default=DEFAULT_LIBRARY, help="教材庫資料夾（預設 ./library）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog", help="列出教材庫中的雜誌、月號、單元與可用題型")

    def add_model_args(p):
        p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude 模型（預設 {DEFAULT_MODEL}）")
        p.add_argument(
            "--effort",
            default=DEFAULT_EFFORT,
            choices=["low", "medium", "high", "xhigh", "max"],
            help=f"思考深度，越高品質越好但越慢越貴（預設 {DEFAULT_EFFORT}）",
        )
        p.add_argument("--out", default="output", help="試卷輸出資料夾（預設 ./output）")

    g = sub.add_parser("generate", help="依出題設定檔產生試卷")
    g.add_argument("--spec", required=True, help="出題設定檔（YAML），見 specs/ 範例")
    g.add_argument("--name", help="輸出檔名（不含副檔名），預設為試卷標題加時間")
    g.add_argument("--dry-run", action="store_true", help="只印出要送給 AI 的命題內容，不呼叫 API")
    add_model_args(g)

    w = sub.add_parser("web", help="啟動網頁介面")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=5000)
    add_model_args(w)
    return parser


def main(argv: list[str] | None = None) -> int:
    import anthropic

    args = build_parser().parse_args(argv)
    handlers = {"catalog": cmd_catalog, "generate": cmd_generate, "web": cmd_web}
    try:
        return handlers[args.command](args)
    except anthropic.AuthenticationError:
        print("錯誤：Claude API 金鑰無效，請設定環境變數 ANTHROPIC_API_KEY。", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"Claude API 錯誤：{e}", file=sys.stderr)
        return 1
    except (LibraryError, GenerationError, ValueError) as e:
        # pydantic 的 ValidationError 也是 ValueError 的子類別
        prefix = "出題設定格式錯誤" if isinstance(e, ValidationError) else "錯誤"
        print(f"{prefix}：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
