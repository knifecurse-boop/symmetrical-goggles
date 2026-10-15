import time
from pathlib import Path

import pytest
import yaml

from exam_generator.generator import ExamGenerator, build_material
from exam_generator.library import LibraryError
from exam_generator.models import ExamSpec, SourceSelection
from exam_generator.question_types import QUESTION_TYPES, validate_section
from exam_generator.render import to_html, to_markdown, write_all
from exam_generator.web import create_app

from conftest import LIBRARY_DIR, FakeClient, fake_section

SPEC_PATH = Path(__file__).resolve().parent.parent / "specs" / "sample_exam.yaml"


def sample_spec() -> ExamSpec:
    return ExamSpec.model_validate(yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")))


# ---------- 教材庫 ----------


def test_library_loads_sample(library):
    mag = library.magazine("sample-english-monthly")
    assert mag.name == "範例英語月刊"
    assert set(mag.issues) == {"2026-09", "2026-10"}
    unit = library.issue("sample-english-monthly", "2026-09").unit("U1")
    assert any(v.word == "sustainable" for v in unit.vocabulary)


def test_resolve_empty_units_means_whole_issue(library):
    units = library.resolve(SourceSelection(magazine="sample-english-monthly", issue="2026-10"))
    assert [u.id for _, _, u in units] == ["U1", "U2"]


def test_resolve_unknown_unit_raises(library):
    with pytest.raises(LibraryError):
        library.resolve(SourceSelection(magazine="sample-english-monthly", issue="2026-09", units=["U9"]))


def test_material_respects_focus(library):
    units = library.resolve(SourceSelection(magazine="sample-english-monthly", issue="2026-09", units=["U1"]))
    vocab_only = build_material(units, ["vocabulary"])
    assert "sustainable" in vocab_only
    assert "It was not until" not in vocab_only
    assert "### 課文" not in vocab_only
    full = build_material(units, ["vocabulary", "grammar", "patterns", "topic"])
    assert "It was not until" in full and "### 課文" in full


# ---------- 題型驗證 ----------


@pytest.mark.parametrize("type_key", list(QUESTION_TYPES))
def test_fake_sections_pass_validation(type_key):
    assert validate_section(QUESTION_TYPES[type_key], 5, fake_section(type_key, 5)) == []


def test_validation_catches_wrong_count_and_answer():
    section = fake_section("vocabulary", 4)
    section.questions[0].answer = "E"
    errors = validate_section(QUESTION_TYPES["vocabulary"], 5, section)
    assert any("題數" in e for e in errors)
    assert any("有效選項代號" in e for e in errors)


def test_validation_catches_bad_blanks_and_duplicate_bank_answers():
    section = fake_section("word_bank", 3)
    section.passage = "Only __(1)__ and __(3)__."
    section.questions[1].answer = "A"
    errors = validate_section(QUESTION_TYPES["word_bank"], 3, section)
    assert any("空格標示" in e for e in errors)
    assert any("重複" in e for e in errors)


# ---------- 產生器 ----------


def test_generate_full_exam(library, fake_client):
    spec = sample_spec()
    exam = ExamGenerator(library, client=fake_client).generate(spec)
    assert [s.type for s in exam.sections] == [s.type for s in spec.sections]
    assert exam.sections[0].title.startswith("一、")
    assert exam.total_points == 100
    assert "範例英語月刊 2026-09 U1、U2" in exam.subtitle

    calls = fake_client.messages.calls
    assert len(calls) == len(spec.sections)
    assert calls[0]["model"] == "claude-opus-5-5"
    assert calls[0]["fallbacks"] == "default"
    # 後面的大題會被告知前面已考過的重點
    assert "已考過" in calls[1]["messages"][0]["content"][-1]["text"]


def test_generate_retries_invalid_output(library):
    client = FakeClient(bad_first=True)
    spec = ExamSpec(
        sources=[SourceSelection(magazine="sample-english-monthly", issue="2026-09")],
        sections=[{"type": "vocabulary", "count": 5}],
    )
    exam = ExamGenerator(library, client=client).generate(spec)
    assert len(client.messages.calls) == 2
    assert "上一次產生的結果不符合格式" in client.messages.calls[1]["messages"][0]["content"][-1]["text"]
    assert len(exam.sections[0].content.questions) == 5


def test_unknown_question_type_fails_before_calling_api(library, fake_client):
    spec = ExamSpec(
        sources=[SourceSelection(magazine="sample-english-monthly", issue="2026-09")],
        sections=[{"type": "vocabulary", "count": 5}, {"type": "essay", "count": 1}],
    )
    with pytest.raises(ValueError, match="essay"):
        ExamGenerator(library, client=fake_client).generate(spec)
    assert fake_client.messages.calls == []


# ---------- 排版 ----------


def test_render_numbers_questions_and_blanks_continuously(library, fake_client):
    exam = ExamGenerator(library, client=fake_client).generate(sample_spec())
    md = to_markdown(exam)
    # 詞彙 10 + 文法 5 → 克漏字從第 16 題開始，文章空格也要跟著改號
    assert "___16___" in md and "___25___" in md
    assert "\n16.\n" in md
    assert "答案" not in md

    key = to_markdown(exam, answers=True)
    assert "答案速查" in key and "1.A" in key


def test_html_escapes_content(library, fake_client):
    exam = ExamGenerator(library, client=fake_client).generate(sample_spec())
    exam.sections[0].content.questions[0].stem = "<script>alert(1)</script>"
    out = to_html(exam)
    assert "<script>alert" not in out
    assert "&lt;script&gt;" in out


def test_write_all_outputs_every_format(library, fake_client, tmp_path):
    exam = ExamGenerator(library, client=fake_client).generate(sample_spec())
    names = {p.name for p in write_all(exam, tmp_path, "exam")}
    assert names == {
        "exam.html", "exam.md", "exam.docx",
        "exam_answers.html", "exam_answers.md", "exam_answers.docx", "exam.json",
    }
    assert (tmp_path / "exam.docx").stat().st_size > 0


# ---------- 網頁介面 ----------


def test_web_generate_flow(tmp_path):
    app = create_app(LIBRARY_DIR, output_dir=tmp_path, client=FakeClient())
    web = app.test_client()

    catalog = web.get("/api/catalog").get_json()
    assert catalog["magazines"][0]["id"] == "sample-english-monthly"
    assert {t["key"] for t in catalog["question_types"]} == set(QUESTION_TYPES)

    bad = web.post("/api/generate", json={"sources": [], "sections": []})
    assert bad.status_code == 400

    spec = sample_spec().model_dump()
    job_id = web.post("/api/generate", json=spec).get_json()["job_id"]
    for _ in range(50):
        status = web.get(f"/api/jobs/{job_id}").get_json()
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    page = web.get(f"/exams/{job_id}/exam.html")
    assert page.status_code == 200 and "高一英文第一次段考" in page.get_data(as_text=True)
    assert web.get(f"/exams/{job_id}/../../etc").status_code == 404
