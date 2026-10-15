"""網頁介面：選擇雜誌 / 月號 / 單元與題型，於背景產生試卷並提供預覽與下載。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from .generator import DEFAULT_EFFORT, DEFAULT_MODEL, ExamGenerator
from .library import Library, LibraryError
from .models import ExamSpec
from .question_types import QUESTION_TYPES, get_type
from .render import write_all

EXAM_STEM = "exam"
DOWNLOADS = {
    # 檔名 -> (mimetype, 是否以附件下載)
    "exam.html": ("text/html", False),
    "exam_answers.html": ("text/html", False),
    "exam.md": ("text/markdown", True),
    "exam_answers.md": ("text/markdown", True),
    "exam.docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
    "exam_answers.docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
    "exam.json": ("application/json", True),
}


@dataclass
class Job:
    id: str
    status: str = "running"  # running / done / error
    log: list[str] = field(default_factory=list)
    error: str = ""


def create_app(
    library_dir: str | Path,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    output_dir: str | Path = "output",
    client=None,
) -> Flask:
    app = Flask(__name__)
    library = Library(library_dir)
    out_root = Path(output_dir).resolve()
    jobs: dict[str, Job] = {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/catalog")
    def catalog():
        types = [
            {"key": qt.key, "name": qt.name, "default_points": qt.default_points}
            for qt in QUESTION_TYPES.values()
        ]
        return jsonify({"magazines": library.catalog(), "question_types": types})

    @app.post("/api/generate")
    def generate():
        try:
            spec = ExamSpec.model_validate(request.get_json(force=True))
            library.resolve_spec(spec)  # 先確認範圍與題型有效
            for s in spec.sections:
                get_type(s.type)
        except (ValueError, LibraryError) as e:  # ValidationError 是 ValueError 的子類別
            return jsonify({"error": str(e)}), 400

        job = Job(id=uuid.uuid4().hex[:12])
        jobs[job.id] = job

        def run():
            gen = ExamGenerator(library, client=client, model=model, effort=effort, on_progress=job.log.append)
            try:
                exam = gen.generate(spec)
                write_all(exam, out_root / job.id, EXAM_STEM)
                job.status = "done"
            except Exception as e:  # noqa: BLE001 — 背景執行緒的錯誤要回報給前端
                job.error = f"{type(e).__name__}: {e}"
                job.status = "error"

        threading.Thread(target=run, daemon=True).start()
        return jsonify({"job_id": job.id})

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            abort(404)
        return jsonify({"status": job.status, "log": job.log, "error": job.error})

    @app.get("/exams/<job_id>/<filename>")
    def download(job_id: str, filename: str):
        if filename not in DOWNLOADS or not job_id.isalnum():
            abort(404)
        path = out_root / job_id / filename
        if not path.exists():
            abort(404)
        mimetype, attachment = DOWNLOADS[filename]
        return send_file(path, mimetype=mimetype, as_attachment=attachment, download_name=filename)

    return app
