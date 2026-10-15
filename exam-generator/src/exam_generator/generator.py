"""呼叫 Claude，依出題設定逐大題產生試題並組成試卷。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .library import Library
from .models import (
    ExamSection,
    ExamSpec,
    Exam,
    Focus,
    GeneratedSection,
    Issue,
    Magazine,
    SectionSpec,
    Unit,
)
from .question_types import QuestionType, get_type, validate_section

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_ATTEMPTS = 3
FALLBACK_BETA = "server-side-fallback-2026-07-01"

CHINESE_NUMERALS = "一二三四五六七八九十"

DIFFICULTY_TEXT = {
    "easy": "偏易：題幹語境明確，干擾選項容易排除，適合基礎複習。",
    "medium": "中等：接近學校段考程度，干擾選項需理解語意才能排除。",
    "hard": "偏難：接近學測/統測進階題，須綜合理解上下文，干擾選項具高度誘答力。",
}

FOCUS_TEXT: dict[Focus, str] = {
    "vocabulary": "單字與片語",
    "grammar": "文法重點",
    "patterns": "句型",
    "topic": "單元主題與課文內容",
}

SYSTEM_PROMPT = """\
你是一位資深的台灣英文科命題老師，熟悉國中會考、高中段考、學測與統測的題型與命題規範。
你會根據老師提供的雜誌單元教材（單字、片語、文法、句型、主題與課文），依指定題型命出高品質的英文試題。

命題原則：
- 只考命題範圍內的教材重點；題目中其他用字應不超過學生程度，避免出現生難字。
- 每題只有一個無爭議的正確答案，干擾選項要合理但明確錯誤。
- 文章與例句須為原創，不可直接照抄課文或教材例句；可以改寫情境、延伸主題。
- 英文須自然道地、合乎文法；解析與說明一律使用繁體中文。
- 避免與已經命過的題目考同一個重點，盡量讓整份試卷涵蓋不同的教材內容。
- 選擇題的正確答案位置要平均分布，不要集中在同一個代號。
"""


def format_unit(magazine: Magazine, issue: Issue, unit: Unit, focus: list[Focus]) -> str:
    """把一個單元的教材轉成給 AI 讀的純文字，只包含勾選的命題重點。"""
    lines = [f"## {magazine.name} {issue.issue} {unit.id}：{unit.title}"]
    if unit.topic:
        lines.append(f"主題：{unit.topic}")
    if "vocabulary" in focus:
        if unit.vocabulary:
            lines.append("### 單字")
            for v in unit.vocabulary:
                lines.append(f"- {v.word} ({v.pos}) {v.meaning}" + (f"｜例：{v.example}" if v.example else ""))
        if unit.phrases:
            lines.append("### 片語")
            for v in unit.phrases:
                lines.append(f"- {v.word} {v.meaning}" + (f"｜例：{v.example}" if v.example else ""))
    if "grammar" in focus and unit.grammar:
        lines.append("### 文法重點")
        for g in unit.grammar:
            lines.append(f"- {g.point}：{g.explanation}")
            lines.extend(f"  - 例：{e}" for e in g.examples)
    if "patterns" in focus and unit.patterns:
        lines.append("### 句型")
        for p in unit.patterns:
            lines.append(f"- {p.pattern}：{p.meaning}")
            lines.extend(f"  - 例：{e}" for e in p.examples)
    if "topic" in focus and unit.article:
        lines.append("### 課文")
        lines.append(unit.article.strip())
    return "\n".join(lines)


def build_material(units: list[tuple[Magazine, Issue, Unit]], focus: list[Focus]) -> str:
    focus_names = "、".join(FOCUS_TEXT[f] for f in focus)
    body = "\n\n".join(format_unit(m, i, u, focus) for m, i, u in units)
    return f"# 命題範圍\n本次命題重點：{focus_names}\n\n{body}"


def build_section_request(
    spec: ExamSpec,
    section: SectionSpec,
    qt: QuestionType,
    used_targets: list[str],
    previous_errors: Optional[list[str]] = None,
) -> str:
    focus = section.focus or spec.focus
    parts = [
        f"請命出「{qt.name}」共 {section.count} 題。",
        f"學生程度：{spec.level}。難度：{DIFFICULTY_TEXT[spec.difficulty]}",
        f"本大題命題重點：{'、'.join(FOCUS_TEXT[f] for f in focus)}。",
        f"題型規範：{qt.guidance}",
    ]
    if spec.notes:
        parts.append(f"整份試卷的額外要求：{spec.notes}")
    if section.instructions:
        parts.append(f"本大題的額外要求：{section.instructions}")
    if used_targets:
        parts.append("前面大題已考過以下重點，請盡量避開，改考其他教材內容：\n" + "\n".join(f"- {t}" for t in used_targets))
    if previous_errors:
        parts.append(
            "上一次產生的結果不符合格式，請修正以下問題後重新命題：\n"
            + "\n".join(f"- {e}" for e in previous_errors)
        )
    return "\n\n".join(parts)


class GenerationError(Exception):
    pass


ProgressCallback = Callable[[str], None]


@dataclass
class ExamGenerator:
    library: Library
    client: object = None  # anthropic.Anthropic；測試時可注入假的 client
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    on_progress: ProgressCallback = field(default=lambda msg: None)

    def _client(self):
        if self.client is None:
            import anthropic

            self.client = anthropic.Anthropic()
        return self.client

    def _call(self, material: str, request: str) -> GeneratedSection:
        try:
            response = self._parse(material, request)
        except TypeError as e:
            # SDK 找不到任何認證資訊時會在送出請求前丟出 TypeError
            if "authentication" in str(e):
                raise GenerationError("找不到 Claude API 金鑰，請先設定環境變數 ANTHROPIC_API_KEY。") from e
            raise
        return self._process(response)

    def _parse(self, material: str, request: str):
        return self._client().beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        # 教材內容在各大題之間相同，設為快取以節省費用
                        {"type": "text", "text": material, "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": request},
                    ],
                }
            ],
            output_format=GeneratedSection,
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

    def _process(self, response) -> GeneratedSection:
        if response.stop_reason == "refusal":
            raise GenerationError("模型拒絕產生此大題，請調整教材內容或命題要求。")
        if response.stop_reason == "max_tokens":
            raise GenerationError("輸出超過長度上限，請減少此大題的題數。")
        parsed = response.parsed_output
        if parsed is None:
            raise GenerationError("模型沒有回傳可解析的試題資料。")
        return parsed

    def generate_section(
        self, spec: ExamSpec, section: SectionSpec, material: str, used_targets: list[str]
    ) -> GeneratedSection:
        qt = get_type(section.type)
        errors: Optional[list[str]] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = build_section_request(spec, section, qt, used_targets, errors)
            result = self._call(material, request)
            errors = validate_section(qt, section.count, result)
            if not errors:
                return result
            self.on_progress(f"  第 {attempt} 次產生的「{qt.name}」格式有誤，重新產生：{'；'.join(errors)}")
        raise GenerationError(f"「{qt.name}」重試 {MAX_ATTEMPTS} 次仍不符合格式：{'；'.join(errors or [])}")

    def generate(self, spec: ExamSpec) -> Exam:
        units = self.library.resolve_spec(spec)
        # 先檢查所有題型代碼，避免跑到一半才失敗
        for s in spec.sections:
            get_type(s.type)

        used_targets: list[str] = []
        sections: list[ExamSection] = []
        for idx, s in enumerate(spec.sections):
            qt = get_type(s.type)
            focus = s.focus or spec.focus
            material = build_material(units, focus)
            self.on_progress(f"產生第 {idx + 1}/{len(spec.sections)} 大題：{qt.name}（{s.count} 題）…")
            content = self.generate_section(spec, s, material, used_targets)
            used_targets.extend(q.source for q in content.questions if q.source)
            numeral = CHINESE_NUMERALS[idx] if idx < len(CHINESE_NUMERALS) else str(idx + 1)
            sections.append(
                ExamSection(
                    type=qt.key,
                    title=f"{numeral}、{s.title or qt.name}",
                    directions=qt.directions,
                    points=s.points,
                    content=content,
                )
            )
        self.on_progress("完成！")
        return Exam(title=spec.title, subtitle=describe_scope(units), sections=sections)


def describe_scope(units: list[tuple[Magazine, Issue, Unit]]) -> str:
    """產生試卷副標題，例如「範例英語月刊 2026-09 U1、U2」。"""
    groups: dict[tuple[str, str], list[str]] = {}
    for m, i, u in units:
        groups.setdefault((m.name, i.issue), []).append(u.id)
    return "；".join(f"{name} {issue} {'、'.join(ids)}" for (name, issue), ids in groups.items())
