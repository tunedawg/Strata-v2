import io
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from .analytics import track_event
from .config import DATASETS_DIR, PORT, STATIC_DIR, TEMPLATES_DIR, ensure_directories
from .extract import extract_document, load_index, save_index
from .redactions import default_redaction_options, result_record, scan_document, summarize_results
from .reports import (
    build_hit_report,
    build_hit_report_pdf,
    build_production_export,
    build_redacted_zip,
    build_redaction_findings_xlsx,
    build_redaction_pdf,
    build_redaction_summary_xlsx,
)
from .search import run_search
from .storage import (
    create_dataset,
    dataset_dir,
    delete_dataset,
    index_file,
    list_dataset_files,
    list_datasets,
    load_manifest,
    save_manifest,
    sanitize_dataset_name,
    touch_dataset,
)


STATE = {
    "loaded_dataset": None,
    "index_status": {"status": "idle", "dataset": "", "done": 0, "total": 0, "message": "No dataset loaded."},
    "redaction_status": {"status": "idle", "dataset": "", "done": 0, "total": 0, "message": "Ready to scan."},
    "loaded_index": {},
    "redaction_results": [],
    "redaction_cancel": False,
}
LOCK = threading.Lock()


def create_app() -> Flask:
    ensure_directories()
    app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATES_DIR))
    app.config["STRATA_PORT"] = PORT

    @app.get("/")
    def root():
        return render_template("index.html")

    @app.get("/production")
    def production_page():
        return render_template("production.html")

    @app.get("/redactions")
    def redactions_page():
        return render_template("redactions.html")

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(str(TEMPLATES_DIR), "favicon.ico", mimetype="image/x-icon")

    @app.get("/favicon.png")
    def favicon_png():
        return send_from_directory(str(TEMPLATES_DIR), "favicon.png", mimetype="image/png")

    @app.get("/api/bootstrap")
    def bootstrap():
        with LOCK:
            loaded = STATE["loaded_dataset"]
            index_status = dict(STATE["index_status"])
            redaction_status = dict(STATE["redaction_status"])
        return jsonify(
            {
                "datasets": [_summary_to_json(item) for item in list_datasets()],
                "loaded_dataset": loaded,
                "index_status": index_status,
                "redaction_status": redaction_status,
            }
        )

    @app.get("/api/datasets")
    def datasets():
        return jsonify({"datasets": [_summary_to_json(item) for item in list_datasets()]})

    @app.post("/api/datasets")
    def datasets_create():
        payload = request.get_json(force=True)
        try:
            name = create_dataset(payload.get("name", ""))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "name": name})

    @app.delete("/api/datasets/<name>")
    def datasets_delete(name: str):
        dataset_name = sanitize_dataset_name(name)
        try:
            delete_dataset(dataset_name)
        except FileNotFoundError:
            return jsonify({"error": "Dataset not found."}), 404
        with LOCK:
            if STATE["loaded_dataset"] == dataset_name:
                STATE["loaded_dataset"] = None
                STATE["loaded_index"] = {}
                STATE["index_status"] = {"status": "idle", "dataset": "", "done": 0, "total": 0, "message": "No dataset loaded."}
        return jsonify({"ok": True})

    @app.post("/api/datasets/<name>/upload")
    def upload(name: str):
        dataset_name = sanitize_dataset_name(name)
        root = dataset_dir(dataset_name)
        if not root.exists():
            return jsonify({"error": "Dataset not found."}), 404
        saved = []
        for file_storage in request.files.getlist("files"):
            relative_name = Path(file_storage.filename.replace("\\", "/"))
            destination = root / relative_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            file_storage.save(destination)
            saved.append(str(relative_name).replace("\\", "/"))
        manifest = {"files": [str(path.relative_to(root)).replace("\\", "/") for path in list_dataset_files(dataset_name)]}
        save_manifest(dataset_name, manifest)
        return jsonify({"ok": True, "saved": saved, "total": len(saved)})

    @app.post("/api/datasets/<name>/index/build")
    def build_index(name: str):
        dataset_name = sanitize_dataset_name(name)
        if not dataset_dir(dataset_name).exists():
            return jsonify({"error": "Dataset not found."}), 404
        threading.Thread(target=_build_index_job, args=(dataset_name,), daemon=True).start()
        return jsonify({"ok": True})

    @app.post("/api/datasets/<name>/index/load")
    def load_dataset_index(name: str):
        dataset_name = sanitize_dataset_name(name)
        index_path = index_file(dataset_name)
        if not index_path.exists():
            return jsonify({"error": "Dataset is not indexed yet."}), 404
        with LOCK:
            STATE["index_status"] = {"status": "loading", "dataset": dataset_name, "done": 0, "total": 0, "message": f"Loading {dataset_name}..."}
        threading.Thread(target=_load_index_job, args=(dataset_name,), daemon=True).start()
        return jsonify({"ok": True})

    @app.get("/api/index/status")
    def index_status():
        with LOCK:
            return jsonify(dict(STATE["index_status"]) | {"loaded_dataset": STATE["loaded_dataset"]})

    @app.post("/api/search")
    def search():
        payload = request.get_json(force=True)
        terms = payload.get("terms", [])
        with LOCK:
            dataset_name = STATE["loaded_dataset"]
            loaded_index = dict(STATE["loaded_index"])
        if not dataset_name or not loaded_index:
            return jsonify({"error": "Load an indexed dataset first."}), 400
        results = run_search(loaded_index, terms)
        track_event("Search Run", {"dataset_name": dataset_name, "term_count": len([term for term in terms if term.strip()])})
        return jsonify({"dataset": dataset_name, "results": results})

    @app.post("/api/production/search")
    def production_search():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        if not index_file(dataset_name).exists():
            return jsonify({"error": "Dataset is not indexed yet."}), 404
        results = run_search(load_index(index_file(dataset_name)), payload.get("terms", []))
        track_event("Production Search", {"dataset_name": dataset_name, "term_count": len([term for term in payload.get("terms", []) if term.strip()])})
        return jsonify({"dataset": dataset_name, "results": results})

    @app.post("/api/exports/hit-report")
    def export_hit_report():
        payload = request.get_json(force=True)
        dataset_name = payload.get("dataset") or STATE["loaded_dataset"] or ""
        format_name = payload.get("format", "xlsx")
        if format_name == "pdf":
            return build_hit_report_pdf(payload.get("results", {}), dataset_name)
        return build_hit_report(payload.get("results", {}), dataset_name)

    @app.post("/api/production/export")
    def export_production():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        selections = payload.get("selections", [])
        track_event("Production Export", {"dataset_name": dataset_name, "selection_count": len(selections)})
        return build_production_export(dataset_dir(dataset_name), dataset_name, selections)

    @app.post("/api/redactions/scan")
    def start_redaction_scan():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        if not dataset_dir(dataset_name).exists():
            return jsonify({"error": "Dataset not found."}), 404
        options = default_redaction_options(payload.get("options", {}))
        with LOCK:
            STATE["redaction_cancel"] = False
        threading.Thread(target=_scan_redactions_job, args=(dataset_name, options), daemon=True).start()
        track_event("Redaction Scan Started", {"dataset_name": dataset_name})
        return jsonify({"ok": True})

    @app.get("/api/redactions/status")
    def redaction_status():
        with LOCK:
            return jsonify(dict(STATE["redaction_status"]))

    @app.get("/api/redactions/results")
    def redaction_results():
        with LOCK:
            results = list(STATE["redaction_results"])
            scanned = STATE["redaction_status"].get("total", 0)
        return jsonify({"results": results, "summary": summarize_results(results, scanned)})

    @app.post("/api/redactions/cancel")
    def cancel_redaction_scan():
        with LOCK:
            STATE["redaction_cancel"] = True
        return jsonify({"ok": True})

    @app.post("/api/redactions/export")
    def export_redactions():
        payload = request.get_json(force=True)
        format_name = payload.get("format", "xlsx")
        with LOCK:
            results = list(STATE["redaction_results"])
            dataset_name = STATE["redaction_status"].get("dataset", "")
            scanned = STATE["redaction_status"].get("total", 0)
        summary = summarize_results(results, scanned)
        if format_name == "zip":
            return build_redacted_zip(dataset_dir(dataset_name), results)
        if format_name == "pdf":
            return build_redaction_pdf(summary, results)
        if format_name == "summary-xlsx":
            return build_redaction_summary_xlsx(summary, results)
        return build_redaction_findings_xlsx(results)

    @app.get("/api/preview/<dataset>/<path:relative_name>")
    def preview(dataset: str, relative_name: str):
        dataset_name = sanitize_dataset_name(dataset)
        root = dataset_dir(dataset_name)
        return send_from_directory(root, relative_name, as_attachment=False)

    @app.get("/preview_file/<dataset>/<path:relative_name>")
    def preview_file(dataset: str, relative_name: str):
        return preview(dataset, relative_name)

    @app.get("/preview/<dataset>/<path:relative_name>")
    def legacy_preview(dataset: str, relative_name: str):
        page = request.args.get("page", "")
        return render_template(
            "preview.html",
            dataset=sanitize_dataset_name(dataset),
            relative_name=relative_name,
            preview_path=quote(relative_name.replace("\\", "/"), safe="/"),
            page=page if page.isdigit() else "",
        )

    @app.get("/datasets")
    def legacy_datasets():
        return jsonify([_summary_to_json(item) for item in list_datasets()])

    @app.post("/datasets/create")
    def legacy_dataset_create():
        return datasets_create()

    @app.post("/datasets/<name>/delete")
    def legacy_dataset_delete(name: str):
        return datasets_delete(name)

    @app.post("/datasets/<name>/upload")
    def legacy_upload(name: str):
        return upload(name)

    @app.post("/datasets/<name>/index")
    def legacy_build_index(name: str):
        return build_index(name)

    @app.post("/datasets/<name>/load")
    def legacy_load_index(name: str):
        return load_dataset_index(name)

    @app.get("/index/status")
    @app.get("/index_status")
    def legacy_index_status():
        with LOCK:
            status = dict(STATE["index_status"])
            loaded = STATE["loaded_dataset"]
            ready = bool(loaded and STATE["loaded_index"] and status.get("status") == "ready")
        return jsonify(status | {"loaded": loaded, "ready": ready})

    @app.post("/search")
    def legacy_search():
        payload = request.get_json(force=True)
        terms = payload.get("terms", [])
        with LOCK:
            dataset_name = STATE["loaded_dataset"]
            loaded_index = dict(STATE["loaded_index"])
        if not dataset_name or not loaded_index:
            return jsonify({"error": "Load an indexed dataset first."}), 400
        modern = run_search(loaded_index, terms)
        track_event("Search Run", {"dataset_name": dataset_name, "term_count": len([term for term in terms if term.strip()])})
        return jsonify({"dataset": dataset_name, "results": _legacy_results(modern)})

    @app.post("/hit_report")
    def legacy_hit_report():
        payload = request.get_json(force=True)
        results = _modern_results_from_legacy(payload.get("results", {}))
        dataset_name = STATE["loaded_dataset"] or ""
        if payload.get("format") == "pdf" or payload.get("fmt") == "pdf":
            return build_hit_report_pdf(results, dataset_name)
        return build_hit_report(results, dataset_name)

    @app.post("/export")
    def legacy_export_search_pdf():
        payload = request.get_json(force=True)
        term = payload.get("term", "search")
        docs = payload.get("docs", [])
        return _simple_search_pdf(term, docs)

    @app.post("/production/search")
    def legacy_production_search():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        if not index_file(dataset_name).exists():
            return jsonify({"error": "Dataset is not indexed yet."}), 404
        modern = run_search(load_index(index_file(dataset_name)), payload.get("terms", []))
        track_event("Production Search", {"dataset_name": dataset_name, "term_count": len([term for term in payload.get("terms", []) if term.strip()])})
        return jsonify({"dataset": dataset_name, "results": _legacy_results(modern)})

    @app.post("/production/export_zip")
    def legacy_export_production_zip():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        legacy_selections = payload.get("selections", [])
        selections = [
            {
                "term": ", ".join(item.get("terms", [])),
                "name": item.get("name", ""),
                "labels": item.get("chunks", []),
                "selected": True,
            }
            for item in legacy_selections
        ]
        track_event("Production Export", {"dataset_name": dataset_name, "selection_count": len(selections)})
        return build_production_export(dataset_dir(dataset_name), dataset_name, selections)

    @app.post("/redactions/scan")
    def legacy_start_redactions():
        payload = request.get_json(force=True)
        dataset_name = sanitize_dataset_name(payload.get("dataset", ""))
        if not dataset_dir(dataset_name).exists():
            return jsonify({"error": "Dataset not found."}), 404
        options = default_redaction_options(payload.get("options", {}))
        with LOCK:
            STATE["redaction_cancel"] = False
        threading.Thread(target=_scan_redactions_job, args=(dataset_name, options), daemon=True).start()
        track_event("Redaction Scan Started", {"dataset_name": dataset_name})
        return jsonify({"status": "started"})

    @app.get("/redactions/status")
    def legacy_redaction_status():
        with LOCK:
            status = dict(STATE["redaction_status"])
        done = status.get("done", 0)
        total = status.get("total", 0) or 1
        return jsonify(status | {"percent": int(done / total * 100)})

    @app.get("/redactions/results")
    def legacy_redaction_results():
        with LOCK:
            results = list(STATE["redaction_results"])
        documents = [_legacy_redaction_record(item) for item in results]
        return jsonify({"documents": documents, "total_findings": sum(item.get("redaction_count", 0) for item in documents)})

    @app.post("/redactions/cancel")
    def legacy_redaction_cancel():
        return cancel_redaction_scan()

    @app.post("/redactions/export_zip")
    def legacy_redaction_zip():
        with LOCK:
            results = list(STATE["redaction_results"])
            dataset_name = STATE["redaction_status"].get("dataset", "")
        return build_redacted_zip(dataset_dir(dataset_name), results)

    @app.post("/redactions/export_list")
    def legacy_redaction_list():
        with LOCK:
            results = list(STATE["redaction_results"])
        return build_redaction_findings_xlsx(results)

    @app.post("/redactions/export_report")
    def legacy_redaction_report():
        fmt = request.args.get("format", "xlsx")
        with LOCK:
            results = list(STATE["redaction_results"])
            scanned = STATE["redaction_status"].get("total", 0)
        summary = summarize_results(results, scanned)
        if fmt == "pdf":
            return build_redaction_pdf(summary, results)
        return build_redaction_summary_xlsx(summary, results)

    track_event("App Launched", {"launched_at": datetime.utcnow().isoformat()})
    return app


def _build_index_job(dataset_name: str) -> None:
    root = dataset_dir(dataset_name)
    files = list_dataset_files(dataset_name)
    with LOCK:
        STATE["index_status"] = {"status": "indexing", "dataset": dataset_name, "done": 0, "total": len(files), "message": f"Indexing {dataset_name}..."}
    index_payload: dict[str, dict] = {}
    for counter, path in enumerate(files, start=1):
        relative_name = str(path.relative_to(root)).replace("\\", "/")
        try:
            index_payload[relative_name] = extract_document(path)
        except Exception as exc:
            index_payload[relative_name] = {"title": path.name, "chunks": [], "error": str(exc)}
        with LOCK:
            STATE["index_status"] = {
                "status": "indexing",
                "dataset": dataset_name,
                "done": counter,
                "total": len(files),
                "message": f"Indexing {path.name}",
            }
    save_index(index_file(dataset_name), index_payload)
    touch_dataset(dataset_name)
    with LOCK:
        STATE["loaded_dataset"] = dataset_name
        STATE["loaded_index"] = index_payload
        STATE["index_status"] = {
            "status": "ready",
            "dataset": dataset_name,
            "done": len(files),
            "total": len(files),
            "message": f"{dataset_name} loaded",
        }
    track_event("Index Built", {"dataset_name": dataset_name, "document_count": len(files)})


def _load_index_job(dataset_name: str) -> None:
    payload = load_index(index_file(dataset_name))
    with LOCK:
        STATE["loaded_dataset"] = dataset_name
        STATE["loaded_index"] = payload
        STATE["index_status"] = {
            "status": "ready",
            "dataset": dataset_name,
            "done": len(payload),
            "total": len(payload),
            "message": f"{dataset_name} loaded",
        }


def _scan_redactions_job(dataset_name: str, options: dict) -> None:
    root = dataset_dir(dataset_name)
    files = [path for path in list_dataset_files(dataset_name) if path.suffix.lower() == ".pdf"]
    with LOCK:
        STATE["redaction_status"] = {"status": "running", "dataset": dataset_name, "done": 0, "total": len(files), "message": "Scanning for redactions..."}
        STATE["redaction_results"] = []
    results = []
    for counter, path in enumerate(files, start=1):
        with LOCK:
            if STATE["redaction_cancel"]:
                STATE["redaction_status"] = {
                    "status": "cancelled",
                    "dataset": dataset_name,
                    "done": counter - 1,
                    "total": len(files),
                    "message": "Scan cancelled.",
                }
                STATE["redaction_results"] = results
                return
        findings = scan_document(path, options)
        if findings:
            results.append(result_record(str(path.relative_to(root)).replace("\\", "/"), findings))
        with LOCK:
            STATE["redaction_results"] = list(results)
            STATE["redaction_status"] = {
                "status": "running",
                "dataset": dataset_name,
                "done": counter,
                "total": len(files),
                "message": f"Scanning {path.name}",
            }
    with LOCK:
        STATE["redaction_results"] = results
        STATE["redaction_status"] = {
            "status": "done",
            "dataset": dataset_name,
            "done": len(files),
            "total": len(files),
            "message": "Redaction scan complete.",
        }


def _legacy_results(results: dict) -> dict:
    legacy = {}
    for term, payload in results.items():
        legacy_docs = []
        for document in payload.get("documents", []):
            legacy_docs.append(
                {
                    "name": document.get("name", ""),
                    "chunks": [match.get("label", match.get("id", "")) for match in document.get("matches", [])],
                }
            )
        legacy[term] = {
            "total_hits": payload.get("total_hits", 0),
            "docs": legacy_docs,
            "document_count": payload.get("document_count", len(legacy_docs)),
        }
    return legacy


def _modern_results_from_legacy(results: dict) -> dict:
    modern = {}
    for term, payload in results.items():
        documents = []
        for document in payload.get("docs", []):
            matches = [
                {
                    "id": chunk,
                    "label": chunk,
                    "page": _page_from_chunk(chunk),
                    "snippet": "",
                }
                for chunk in document.get("chunks", [])
            ]
            documents.append(
                {
                    "name": document.get("name", ""),
                    "title": Path(document.get("name", "")).name,
                    "matches": matches,
                    "match_count": len(matches),
                }
            )
        modern[term] = {
            "total_hits": payload.get("total_hits", sum(len(item.get("matches", [])) for item in documents)),
            "document_count": len(documents),
            "documents": documents,
        }
    return modern


def _legacy_redaction_record(result: dict) -> dict:
    return {
        "filename": result.get("filename", ""),
        "redaction_count": result.get("finding_count", 0),
        "pages": result.get("pages", []),
        "type_summary": result.get("finding_types", {}),
        "findings": result.get("findings", []),
    }


def _page_from_chunk(chunk: str) -> int | None:
    if not chunk:
        return None
    if chunk.startswith("p"):
        digits = []
        for char in chunk[1:]:
            if char.isdigit():
                digits.append(char)
            else:
                break
        if digits:
            return int("".join(digits))
    return None


def _simple_search_pdf(term: str, docs: list[dict]):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    rows = [["Document", "Matching Chunks"]]
    for item in docs:
        rows.append([item.get("name", ""), ", ".join(item.get("chunks", []))])
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#334155")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    document.build([Paragraph(f"Strata Search Export: {term}", styles["Title"]), Spacer(1, 12), table])
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="search_export.pdf", mimetype="application/pdf")


def _summary_to_json(summary) -> dict:
    return {
        "name": summary.name,
        "indexed": summary.indexed,
        "files": summary.file_count,
        "file_count": summary.file_count,
        "updated_at": summary.updated_at,
        "manifest_file_count": len(load_manifest(summary.name).get("files", [])),
    }
