import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from exam_generator.library import Library
from exam_generator.models import GeneratedSection, Question
from exam_generator.question_types import QUESTION_TYPES

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "library"


def fake_section(type_key: str, count: int) -> GeneratedSection:
    """產生一個符合題型格式的假大題。"""
    qt = QUESTION_TYPES[type_key]
    passage = None
    bank: list[str] = []
    if qt.layout in ("passage_mc", "word_bank"):
        if type_key in ("cloze", "word_bank"):
            passage = "Intro. " + " ".join(f"Word __({i})__ here." for i in range(1, count + 1))
        else:
            passage = "A reading passage about sustainable habits."
    if qt.layout == "word_bank":
        bank = [f"word{i}" for i in range(max(10, count))]
    questions = []
    for i in range(count):
        if qt.layout in ("mc", "passage_mc"):
            q = Question(stem=f"Q{i} ___ .", options=["alpha", "beta", "gamma", "delta"],
                         answer="ABCD"[i % 4], explanation="解析", source=f"{type_key} target {i}")
        elif qt.layout == "word_bank":
            q = Question(stem=f"({i + 1})", options=[], answer="ABCDEFGHIJKLMNOP"[i],
                         explanation="解析", source=f"{type_key} target {i}")
        else:
            q = Question(stem=f"中文句子 {i}", options=[], answer=f"Reference answer {i}.",
                         explanation="評分重點", source=f"{type_key} target {i}")
        questions.append(q)
    return GeneratedSection(passage=passage, word_bank=bank, questions=questions)


class FakeMessages:
    """模擬 client.beta.messages.parse：依請求文字判斷題型與題數，回傳格式正確的大題。"""

    def __init__(self, bad_first: bool = False):
        self.calls: list[dict] = []
        self.bad_first = bad_first

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        request = kwargs["messages"][0]["content"][-1]["text"]
        name = re.search(r"請命出「(.+?)」共 (\d+) 題", request)
        type_key = next(k for k, qt in QUESTION_TYPES.items() if qt.name == name.group(1))
        count = int(name.group(2))
        if self.bad_first and len(self.calls) == 1:
            count -= 1  # 第一次故意少一題，觸發重試
        return SimpleNamespace(stop_reason="end_turn", parsed_output=fake_section(type_key, count))


class FakeClient:
    def __init__(self, bad_first: bool = False):
        self.messages = FakeMessages(bad_first)
        self.beta = SimpleNamespace(messages=self.messages)


@pytest.fixture
def library() -> Library:
    return Library(LIBRARY_DIR)


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()
