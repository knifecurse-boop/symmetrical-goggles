"""題型定義：每種題型的名稱、作答說明、命題指引與輸出驗證規則。

新增題型只要在 QUESTION_TYPES 加一筆 QuestionType 即可，
產生器、網頁介面與試卷排版都會自動支援。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import GeneratedSection

Layout = Literal["mc", "passage_mc", "word_bank", "open"]

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class QuestionType:
    key: str
    name: str  # 中文名稱
    directions: str  # 印在試卷上的作答說明
    guidance: str  # 給 AI 的命題指引
    layout: Layout
    option_count: int = 4  # 選擇題選項數
    default_points: float = 2


QUESTION_TYPES: dict[str, QuestionType] = {
    qt.key: qt
    for qt in [
        QuestionType(
            key="vocabulary",
            name="詞彙題",
            directions="每題選出一個最適當的選項。",
            guidance=(
                "單句四選一詞彙題。每題考一個命題範圍內的單字或片語，題幹提供足夠語境讓答案唯一。"
                "四個選項須為同詞性、同時態/形式，且干擾選項在字形或語意上有合理誘答力，"
                "但放入句中明顯不通順。正確答案在 A-D 間平均分布。"
            ),
            layout="mc",
        ),
        QuestionType(
            key="grammar",
            name="文法選擇題",
            directions="每題選出一個最適當的選項，使句子合乎文法。",
            guidance=(
                "單句四選一文法題，聚焦命題範圍內的文法重點與句型。"
                "選項為同一字詞或結構的不同形式（時態、語態、分詞、關係詞、連接詞等），只有一個合乎文法。"
            ),
            layout="mc",
        ),
        QuestionType(
            key="cloze",
            name="綜合測驗（克漏字）",
            directions="閱讀下文，每個空格選出一個最適當的選項，使文意通順。",
            guidance=(
                "撰寫一篇 150-250 字、與單元主題相關的全新短文（不可照抄課文），"
                "在文中挖空，以 __(1)__、__(2)__ 依序標示，空格數等於題數。"
                "空格混合考單字、片語、文法、轉折語與上下文理解。"
                "questions 依空格順序排列，stem 填空格編號如 '(1)'，每題四個選項。"
            ),
            layout="passage_mc",
        ),
        QuestionType(
            key="word_bank",
            name="文意選填",
            directions="閱讀下文，從字詞庫中選出最適當的選項填入空格，每個選項只能用一次。",
            guidance=(
                "撰寫一篇 150-250 字、與單元主題相關的全新短文，以 __(1)__、__(2)__ 依序標示空格，"
                "空格數等於題數。word_bank 提供 10 個單字（若題數超過 10，則等於題數），"
                "優先使用命題範圍內的單字，形式須與空格相符；多出來的為干擾字，詞性要多元。"
                "questions 依空格順序，stem 填空格編號如 '(1)'，options 給空陣列，"
                "answer 為字詞庫中對應的代號（A, B, C...），每個代號最多用一次。"
            ),
            layout="word_bank",
            option_count=0,
        ),
        QuestionType(
            key="reading",
            name="閱讀測驗",
            directions="閱讀下文，回答所附問題，每題選出一個最適當的選項。",
            guidance=(
                "撰寫一篇 250-350 字、延伸單元主題的全新文章（不可照抄課文），自然融入命題範圍內的單字與句型。"
                "題目涵蓋主旨、細節、推論、字義猜測、作者態度等不同層次，每題四個選項，答案須能從文章判斷。"
            ),
            layout="passage_mc",
        ),
        QuestionType(
            key="translation",
            name="中譯英",
            directions="將下列中文句子譯成正確、通順的英文。",
            guidance=(
                "每題給一句繁體中文句子（stem），要求學生譯成英文，且須用到命題範圍內的指定單字或句型。"
                "可在中文句後以括號提示必須使用的單字或句型，例如（not until）。"
                "options 給空陣列，answer 給一個標準參考譯文，explanation 說明評分重點與可接受的其他寫法。"
            ),
            layout="open",
            option_count=0,
            default_points=4,
        ),
        QuestionType(
            key="sentence_combination",
            name="句子合併",
            directions="依括號內的提示，將兩個句子合併成一句。",
            guidance=(
                "每題 stem 給兩個英文短句，並在後面以括號提示要使用的句型或連接詞，"
                "例如 'He was tired. He kept working. (Although)'。合併必須練習命題範圍內的文法或句型。"
                "options 給空陣列，answer 為合併後的參考答案。"
            ),
            layout="open",
            option_count=0,
            default_points=3,
        ),
    ]
}


def get_type(key: str) -> QuestionType:
    try:
        return QUESTION_TYPES[key]
    except KeyError:
        valid = "、".join(QUESTION_TYPES)
        raise ValueError(f"未知的題型「{key}」，可用題型：{valid}") from None


_BLANK_RE = re.compile(r"__\((\d+)\)__")


def validate_section(qt: QuestionType, count: int, section: GeneratedSection) -> list[str]:
    """檢查 AI 產生的大題是否符合題型格式，回傳錯誤訊息清單（空清單代表通過）。"""
    errors: list[str] = []
    qs = section.questions
    if len(qs) != count:
        errors.append(f"題數應為 {count} 題，實際產生 {len(qs)} 題。")

    if qt.layout in ("mc", "passage_mc"):
        valid_letters = LETTERS[: qt.option_count]
        for i, q in enumerate(qs, 1):
            if len(q.options) != qt.option_count:
                errors.append(f"第 {i} 題應有 {qt.option_count} 個選項，實際 {len(q.options)} 個。")
            if q.answer.strip().upper() not in valid_letters:
                errors.append(f"第 {i} 題答案「{q.answer}」不是有效選項代號（{valid_letters}）。")
            if len({o.strip().lower() for o in q.options}) != len(q.options):
                errors.append(f"第 {i} 題有重複的選項。")

    if qt.layout in ("passage_mc", "word_bank"):
        if not section.passage or not section.passage.strip():
            errors.append("此題型需要文章（passage），但沒有產生。")

    if qt.key in ("cloze", "word_bank") and section.passage:
        blanks = [int(n) for n in _BLANK_RE.findall(section.passage)]
        expected = list(range(1, count + 1))
        if blanks != expected:
            errors.append(
                f"文章中的空格標示應依序為 __(1)__ 到 __({count})__，實際找到 {blanks}。"
            )

    if qt.layout == "word_bank":
        bank = section.word_bank
        if len(bank) < count:
            errors.append(f"字詞庫只有 {len(bank)} 個字，少於題數 {count}。")
        valid_letters = LETTERS[: len(bank)]
        used = [q.answer.strip().upper() for q in qs]
        for i, a in enumerate(used, 1):
            if a not in valid_letters:
                errors.append(f"第 {i} 題答案「{a}」不在字詞庫代號範圍內。")
        if len(set(used)) != len(used):
            errors.append("文意選填的答案代號重複使用。")

    if qt.layout == "open":
        for i, q in enumerate(qs, 1):
            if not q.answer.strip():
                errors.append(f"第 {i} 題缺少參考答案。")

    return errors
