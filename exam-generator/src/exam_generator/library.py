"""讀取教材庫：library/<雜誌代碼>/magazine.yaml + 每期一個 <月號>.yaml。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ExamSpec, Issue, Magazine, SourceSelection, Unit

MAGAZINE_FILE = "magazine.yaml"


class LibraryError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise LibraryError(f"{path} 不是有效的 YAML：{e}") from e
    if not isinstance(data, dict):
        raise LibraryError(f"{path} 內容應為 YAML 物件（key: value）")
    return data


def load_magazine(directory: Path) -> Magazine:
    meta_path = directory / MAGAZINE_FILE
    meta = _load_yaml(meta_path) if meta_path.exists() else {}
    issues: dict[str, Issue] = {}
    for path in sorted(directory.glob("*.yaml")):
        if path.name == MAGAZINE_FILE:
            continue
        data = _load_yaml(path)
        data.setdefault("issue", path.stem)
        try:
            issue = Issue.model_validate(data)
        except ValidationError as e:
            raise LibraryError(f"{path} 格式錯誤：\n{e}") from e
        issues[issue.issue] = issue
    return Magazine(
        id=directory.name,
        name=meta.get("name", directory.name),
        level=meta.get("level", ""),
        issues=issues,
    )


class Library:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        if not self.root.is_dir():
            raise LibraryError(f"找不到教材庫資料夾：{self.root}")
        self.magazines: dict[str, Magazine] = {}
        for d in sorted(p for p in self.root.iterdir() if p.is_dir()):
            self.magazines[d.name] = load_magazine(d)

    def magazine(self, magazine_id: str) -> Magazine:
        try:
            return self.magazines[magazine_id]
        except KeyError:
            raise LibraryError(f"教材庫中沒有雜誌「{magazine_id}」") from None

    def issue(self, magazine_id: str, issue_id: str) -> Issue:
        mag = self.magazine(magazine_id)
        try:
            return mag.issues[issue_id]
        except KeyError:
            raise LibraryError(f"雜誌「{mag.name}」沒有 {issue_id} 這一期") from None

    def resolve(self, selection: SourceSelection) -> list[tuple[Magazine, Issue, Unit]]:
        mag = self.magazine(selection.magazine)
        issue = self.issue(selection.magazine, selection.issue)
        if not selection.units:
            return [(mag, issue, u) for u in issue.units]
        try:
            return [(mag, issue, issue.unit(uid)) for uid in selection.units]
        except KeyError as e:
            raise LibraryError(f"雜誌「{mag.name}」{e.args[0]}") from None

    def resolve_spec(self, spec: ExamSpec) -> list[tuple[Magazine, Issue, Unit]]:
        units = []
        for sel in spec.sources:
            units.extend(self.resolve(sel))
        return units

    def catalog(self) -> list[dict]:
        """給網頁介面用的目錄：雜誌 → 月號 → 單元。"""
        return [
            {
                "id": m.id,
                "name": m.name,
                "level": m.level,
                "issues": [
                    {
                        "id": i.issue,
                        "title": i.title,
                        "units": [
                            {
                                "id": u.id,
                                "title": u.title,
                                "topic": u.topic,
                                "vocab_count": len(u.vocabulary) + len(u.phrases),
                                "grammar": [g.point for g in u.grammar],
                                "patterns": [p.pattern for p in u.patterns],
                            }
                            for u in i.units
                        ],
                    }
                    for i in sorted(m.issues.values(), key=lambda i: i.issue, reverse=True)
                ],
            }
            for m in self.magazines.values()
        ]
