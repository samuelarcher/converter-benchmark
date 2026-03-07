"""Converter Benchmarking Flask App."""
from __future__ import annotations
import json
import os
from pathlib import Path

from flask import (
    Flask, redirect, render_template, request, url_for, flash, abort,
    send_from_directory
)

import db
from config import (
    OUTPUT_FORMATS, get_default_output_format, set_default_output_format
)
from converters import list_converters, get_converter

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "benchmark-dev-secret")

# Initialise DB on startup
db.init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_extensions() -> set[str]:
    exts = set()
    for conv in list_converters():
        exts.update(conv.supported_extensions)
    return exts


def _converters_for_ext(ext: str) -> list:
    return [c for c in list_converters() if ext.lower() in c.supported_extensions]


def _run_conversion(doc_id: int, file_path: Path, converter_name: str, output_format: str):
    conv = get_converter(converter_name)
    if not conv:
        return
    result = conv.convert(file_path, output_format)
    db.upsert_conversion(
        document_id=doc_id,
        converter_name=converter_name,
        output_format=output_format,
        content=result.content,
        error=result.error,
        duration_ms=result.duration_ms,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    docs = db.get_doc_summary()
    converters = list_converters()
    default_fmt = get_default_output_format()
    return render_template(
        "index.html",
        docs=docs,
        converters=converters,
        output_formats=OUTPUT_FORMATS,
        default_fmt=default_fmt,
    )


@app.route("/settings", methods=["POST"])
def update_settings():
    fmt = request.form.get("default_output_format", "markdown")
    if fmt in OUTPUT_FORMATS:
        set_default_output_format(fmt)
        flash(f"Default output format set to '{fmt}'", "success")
    else:
        flash("Invalid format", "error")
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("index"))
    f = request.files["file"]
    if not f.filename:
        flash("No file selected", "error")
        return redirect(url_for("index"))
    filename = Path(f.filename).name
    dest = UPLOAD_DIR / filename
    # Avoid overwriting: add suffix if needed
    counter = 1
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    while dest.exists():
        dest = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
    f.save(dest)
    doc_id = db.insert_document(
        filename=dest.name,
        file_path=str(dest),
        file_ext=suffix.lower(),
    )
    flash(f"Uploaded '{dest.name}'", "success")
    return redirect(url_for("doc_results", doc_id=doc_id))


@app.route("/scan", methods=["POST"])
def scan():
    folder = request.form.get("folder_path", "").strip()
    if not folder:
        flash("No folder path provided", "error")
        return redirect(url_for("index"))
    p = Path(folder).expanduser()
    if not p.is_dir():
        flash(f"'{folder}' is not a directory", "error")
        return redirect(url_for("index"))
    exts = _all_extensions()
    added = 0
    for f in p.rglob("*"):
        if f.suffix.lower() in exts and f.is_file():
            if not db.document_exists(str(f)):
                db.insert_document(
                    filename=f.name,
                    file_path=str(f),
                    file_ext=f.suffix.lower(),
                )
                added += 1
    flash(f"Scanned '{folder}': added {added} document(s)", "success")
    return redirect(url_for("index"))


@app.route("/doc/<int:doc_id>")
def doc_results(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    conversions = db.get_conversions_for_doc(doc_id)
    scores = db.get_scores_for_doc(doc_id)

    # Build score lookup: conv_id -> {scorer: score_row}
    score_map: dict[int, dict] = {}
    for s in scores:
        cid = s["conversion_id"]
        score_map.setdefault(cid, {})
        score_map[cid][s["scorer"]] = dict(s)

    # Group conversions by output_format
    grouped: dict[str, list] = {}
    for c in conversions:
        fmt = c["output_format"]
        grouped.setdefault(fmt, [])
        grouped[fmt].append(dict(c))

    ext = doc["file_ext"].lower()
    available_converters = _converters_for_ext(ext)
    default_fmt = get_default_output_format()

    return render_template(
        "results.html",
        doc=doc,
        grouped=grouped,
        score_map=score_map,
        available_converters=available_converters,
        output_formats=OUTPUT_FORMATS,
        default_fmt=default_fmt,
    )


@app.route("/doc/<int:doc_id>/run", methods=["POST"])
def run_converters(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    selected = request.form.getlist("converters[]")
    output_format = request.form.get("output_format") or get_default_output_format()
    if output_format not in OUTPUT_FORMATS:
        output_format = get_default_output_format()
    file_path = Path(doc["file_path"])
    if not file_path.exists():
        flash(f"File not found: {file_path}", "error")
        return redirect(url_for("doc_results", doc_id=doc_id))
    ran = 0
    for name in selected:
        conv = get_converter(name)
        if not conv:
            continue
        if output_format not in conv.supported_output_formats:
            flash(
                f"'{conv.label}' does not support '{output_format}' — skipped",
                "warning",
            )
            continue
        _run_conversion(doc_id, file_path, name, output_format)
        ran += 1
    flash(f"Ran {ran} converter(s) in '{output_format}' format", "success")
    return redirect(url_for("doc_results", doc_id=doc_id))


@app.route("/doc/<int:doc_id>/review")
def review(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    fmt_filter = request.args.get("fmt", None)
    conversions = db.get_conversions_for_doc(doc_id)
    scores = db.get_scores_for_doc(doc_id)

    score_map: dict[int, dict] = {}
    for s in scores:
        cid = s["conversion_id"]
        score_map.setdefault(cid, {})
        score_map[cid][s["scorer"]] = dict(s)

    if fmt_filter:
        conversions = [c for c in conversions if c["output_format"] == fmt_filter]

    grouped: dict[str, list] = {}
    for c in conversions:
        grouped.setdefault(c["output_format"], []).append(dict(c))

    available_formats = sorted({c["output_format"] for c in db.get_conversions_for_doc(doc_id)})

    return render_template(
        "review.html",
        doc=doc,
        grouped=grouped,
        score_map=score_map,
        available_formats=available_formats,
        fmt_filter=fmt_filter,
    )


@app.route("/doc/<int:doc_id>/score", methods=["POST"])
def save_scores(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    saved = 0
    for key, value in request.form.items():
        if key.startswith("score_"):
            conv_id = int(key.split("_")[1])
            notes_key = f"notes_{conv_id}"
            score_val = value.strip()
            if score_val.isdigit():
                db.upsert_score(
                    conversion_id=conv_id,
                    scorer="human",
                    score=int(score_val),
                    notes=request.form.get(notes_key, ""),
                    rubric="",
                )
                saved += 1
    flash(f"Saved {saved} human score(s)", "success")
    return redirect(url_for("review", doc_id=doc_id))


@app.route("/doc/<int:doc_id>/llm-score", methods=["POST"])
def llm_score(doc_id: int):
    doc = db.get_document(doc_id)
    if not doc:
        abort(404)
    conversions = [dict(c) for c in db.get_conversions_for_doc(doc_id)]

    from scoring.llm_scorer import score_all_conversions
    results = score_all_conversions(conversions, filename=doc["filename"])

    saved = 0
    for conv_id, (rubric, overall) in results.items():
        db.upsert_score(
            conversion_id=conv_id,
            scorer="llm",
            score=overall,
            notes="",
            rubric=json.dumps(rubric),
        )
        saved += 1
    if saved:
        flash(f"LLM scored {saved} conversion(s)", "success")
    else:
        flash("No conversions scored (check ANTHROPIC_API_KEY and that conversions exist)", "warning")
    return redirect(url_for("doc_results", doc_id=doc_id))


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

import markdown as md_lib

@app.template_filter("render_content")
def render_content_filter(content: str, output_format: str) -> str:
    if not content:
        return ""
    if output_format == "markdown":
        return md_lib.markdown(content, extensions=["tables", "fenced_code"])
    if output_format == "html":
        return content
    return content  # text/json handled in template


@app.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, threaded=False)
