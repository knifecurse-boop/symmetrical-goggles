"""資料模型：雜誌教材內容、出題設定、以及 AI 產生的試題。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 教材內容（雜誌 / 月號 / 單元）
# ---------------------------------------------------------------------------


class VocabItem(BaseModel):
    word: str
    pos: str = ""  # 詞性，例如 n. / v. / adj.
    meaning: str = ""  # 中文解釋
    example: str = ""


class GrammarPoint(BaseModel):
    point: str  # 文法重點名稱，例如「分詞構句」
    explanation: str = ""
    examples: list[str] = Field(default_factory=list)


class SentencePattern(BaseModel):
    pattern: str  # 句型，例如「It is not until ... that ...」
    meaning: str = ""
    examples: list[str] = Field(default_factory=list)


class Unit(BaseModel):
    id: str
    title: str
    topic: str = ""  # 單元主題
    article: str = ""  # 課文內容
    vocabulary: list[VocabItem] = Field(default_factory=list)
    phrases: list[VocabItem] = Field(default_factory=list)  # 片語
    grammar: list[GrammarPoint] = Field(default_factory=list)
    patterns: list[SentencePattern] = Field(default_factory=list)


class Issue(BaseModel):
    issue: str  # 月號，例如 2026-09
    title: str = ""
    units: list[Unit] = Field(default_factory=list)

    def unit(self, unit_id: str) -> Unit:
        for u in self.units:
            if u.id == unit_id:
                return u
        raise KeyError(f"月號 {self.issue} 找不到單元 {unit_id}")


class Magazine(BaseModel):
    id: str
    name: str
    level: str = ""  # 適用程度，例如「高中」「CEFR B1-B2」
    issues: dict[str, Issue] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 出題設定
# ---------------------------------------------------------------------------

Focus = Literal["vocabulary", "grammar", "patterns", "topic"]
ALL_FOCUS: tuple[Focus, ...] = ("vocabulary", "grammar", "patterns", "topic")


class SourceSelection(BaseModel):
    """選擇一本雜誌某一期的哪些單元作為命題範圍。"""

    magazine: str
    issue: str
    units: list[str] = Field(default_factory=list)  # 空白代表整期所有單元


class SectionSpec(BaseModel):
    type: str  # 題型代碼，見 question_types.QUESTION_TYPES
    count: int = Field(gt=0, le=50)  # 題數
    points: float = Field(default=2, gt=0)  # 每題分數
    title: Optional[str] = None  # 覆寫大題標題
    focus: Optional[list[Focus]] = None  # 覆寫整份試卷的命題重點
    instructions: str = ""  # 額外命題要求，例如「選項須為同詞性」


class ExamSpec(BaseModel):
    title: str = "英文測驗卷"
    level: str = "高中"  # 給 AI 的程度說明
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    focus: list[Focus] = Field(default_factory=lambda: list(ALL_FOCUS))
    sources: list[SourceSelection] = Field(min_length=1)
    sections: list[SectionSpec] = Field(min_length=1)
    notes: str = ""  # 給 AI 的整體額外要求


# ---------------------------------------------------------------------------
# AI 產生的試題（同時作為 structured output 的 schema）
# ---------------------------------------------------------------------------


class Question(BaseModel):
    stem: str = Field(
        description="題幹。選擇題為含空格（___）的句子或問題；克漏字/文意選填為空格編號，例如 '(1)'；"
        "翻譯/句子合併為要作答的中文句子或待合併的英文句子。"
    )
    options: list[str] = Field(
        description="選項文字（不含 A/B/C/D 代號）。非選擇題（翻譯、句子合併、文意選填）請給空陣列。"
    )
    answer: str = Field(
        description="正確答案。選擇題為選項代號 A/B/C/D；文意選填為字詞庫代號 A-J；"
        "翻譯與句子合併為參考答案英文句子。"
    )
    explanation: str = Field(description="繁體中文解析，說明為何正確、其他選項為何錯誤。")
    source: str = Field(description="命題依據，例如『U1 單字 sustainable』或『U2 句型 not only... but also』。")


class GeneratedSection(BaseModel):
    passage: Optional[str] = Field(
        description="克漏字、文意選填、閱讀測驗用的文章；空格以 __(1)__、__(2)__ 依序標示。其他題型為 null。"
    )
    word_bank: list[str] = Field(
        description="文意選填的字詞庫（依 A、B、C... 順序，不含代號），其他題型給空陣列。"
    )
    questions: list[Question]


class ExamSection(BaseModel):
    type: str
    title: str
    directions: str
    points: float
    content: GeneratedSection


class Exam(BaseModel):
    title: str
    subtitle: str = ""
    sections: list[ExamSection]

    @property
    def total_points(self) -> float:
        return sum(s.points * len(s.content.questions) for s in self.sections)
