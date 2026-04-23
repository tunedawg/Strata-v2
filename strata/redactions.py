from collections import Counter
from pathlib import Path


def default_redaction_options(options: dict | None = None) -> dict:
    requested = options or {}
    return {
        "annotations": bool(requested.get("annotations", True)),
        "black_bars": bool(requested.get("black_bars", True)),
        "drawn_redactions": bool(requested.get("drawn_redactions", True)),
        "white_boxes": False,
        "hidden_text": False,
        "docx_hidden_text": False,
    }


def _color_is_dark(color) -> bool:
    if color is None:
        return False
    try:
        if isinstance(color, (int, float)):
            return float(color) < 0.15
        if isinstance(color, (list, tuple)):
            if len(color) == 1:
                return float(color[0]) < 0.15
            if len(color) >= 3:
                return all(float(value) < 0.2 for value in color[:3])
    except Exception:
        return False
    return False


def _color_is_white(color) -> bool:
    if color is None:
        return False
    try:
        if isinstance(color, (int, float)):
            return float(color) > 0.92
        if isinstance(color, (list, tuple)):
            if len(color) == 1:
                return float(color[0]) > 0.92
            if len(color) >= 3:
                return all(float(value) > 0.92 for value in color[:3])
    except Exception:
        return False
    return False


def _detect_drawn_redactions(path: Path, page_number: int) -> list[dict]:
    from pdf2image import convert_from_path

    findings: list[dict] = []
    try:
        images = convert_from_path(str(path), dpi=110, first_page=page_number, last_page=page_number, grayscale=True)
    except Exception:
        return findings
    if not images:
        return findings

    image = images[0]
    width, height = image.size
    pixels = image.load()
    visited: set[tuple[int, int]] = set()
    stride = 2

    def is_dark(x: int, y: int) -> bool:
        return pixels[x, y] < 45

    for y in range(0, height, stride):
        for x in range(0, width, stride):
            if (x, y) in visited or not is_dark(x, y):
                continue
            stack = [(x, y)]
            visited.add((x, y))
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx + stride, cy), (cx - stride, cy), (cx, cy + stride), (cx, cy - stride)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or (nx, ny) in visited:
                        continue
                    if is_dark(nx, ny):
                        visited.add((nx, ny))
                        stack.append((nx, ny))
            box_width = max_x - min_x + stride
            box_height = max_y - min_y + stride
            area = count * stride * stride
            aspect = box_width / max(box_height, 1)
            fill_ratio = area / max(box_width * box_height, 1)
            if box_width >= 55 and box_height >= 8 and aspect >= 3 and fill_ratio >= 0.28:
                findings.append(
                    {
                        "page": page_number,
                        "type": "Drawn/Sharpie Redaction",
                        "details": f"Dark scanned-page mark {box_width}x{box_height} px.",
                        "location": f"({min_x}, {min_y}, {max_x}, {max_y}) px",
                    }
                )
    return findings[:20]


def detect_pdf_redactions(path: Path, options: dict) -> list[dict]:
    import pdfplumber
    import pypdf

    options = default_redaction_options(options)
    findings: list[dict] = []
    if options.get("annotations", True):
        try:
            reader = pypdf.PdfReader(str(path), strict=False)
            for page_number, page in enumerate(reader.pages, start=1):
                for annotation in page.get("/Annots") or []:
                    try:
                        annotation_object = annotation.get_object() if hasattr(annotation, "get_object") else annotation
                        subtype = str(annotation_object.get("/Subtype", ""))
                        if subtype == "/Redact":
                            findings.append(
                                {
                                    "page": page_number,
                                    "type": "PDF Redact Annotation",
                                    "details": "Standard /Redact annotation detected.",
                                }
                            )
                    except Exception:
                        continue
        except Exception:
            pass
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                if options.get("black_bars", True):
                    for rect in page.rects or []:
                        width = abs(float(rect.get("x1", 0)) - float(rect.get("x0", 0)))
                        height = abs(float(rect.get("bottom", 0)) - float(rect.get("top", 0)))
                        if width > 18 and height > 4 and _color_is_dark(rect.get("non_stroking_color")):
                            findings.append(
                                {
                                    "page": page_number,
                                    "type": "Manual PDF Redaction",
                                    "details": f"Dark filled rectangle {width:.0f}x{height:.0f} pt.",
                                }
                            )
                if options.get("white_boxes", True):
                    for rect in page.rects or []:
                        width = abs(float(rect.get("x1", 0)) - float(rect.get("x0", 0)))
                        height = abs(float(rect.get("bottom", 0)) - float(rect.get("top", 0)))
                        if width > 18 and height > 4 and _color_is_white(rect.get("non_stroking_color")):
                            findings.append(
                                {
                                    "page": page_number,
                                    "type": "White-Out Box",
                                    "details": f"White filled rectangle {width:.0f}x{height:.0f} pt.",
                                }
                            )
                if options.get("hidden_text", True):
                    for char in page.chars or []:
                        text = (char.get("text") or "").strip()
                        if text and _color_is_white(char.get("non_stroking_color")):
                            findings.append(
                                {
                                    "page": page_number,
                                    "type": "Hidden/White Text Heuristic",
                                    "details": f"White text detected: {text[:32]}",
                                }
                            )
                            break
                if options.get("drawn_redactions", True):
                    findings.extend(_detect_drawn_redactions(path, page_number))
    except Exception:
        pass
    return findings


def detect_docx_redactions(path: Path, options: dict) -> list[dict]:
    from docx import Document

    if not options.get("docx_hidden_text", True):
        return []

    findings = []
    document = Document(str(path))
    for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
        for run in paragraph.runs:
            text = (run.text or "").strip()
            if not text:
                continue
            if run.font.hidden:
                findings.append(
                    {
                        "page": None,
                        "type": "DOCX Hidden Text",
                        "details": f"Paragraph {paragraph_index}: hidden run '{text[:40]}'",
                    }
                )
            color = getattr(run.font.color, "rgb", None)
            if color and str(color).upper() in {"FFFFFF", "FFFFFFFF"}:
                findings.append(
                    {
                        "page": None,
                        "type": "DOCX White Text",
                        "details": f"Paragraph {paragraph_index}: white text '{text[:40]}'",
                    }
                )
    return findings


def scan_document(path: Path, options: dict) -> list[dict]:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return detect_pdf_redactions(path, options)
    if extension in {".docx", ".doc"} and default_redaction_options(options).get("docx_hidden_text", False):
        return detect_docx_redactions(path, options)
    return []


def summarize_results(results: list[dict], files_scanned: int | None = None) -> dict:
    scanned = len(results) if files_scanned is None else files_scanned
    with_redactions = sum(1 for result in results if result["finding_count"] > 0)
    total_findings = sum(result["finding_count"] for result in results)
    return {
        "files_scanned": scanned,
        "with_redactions": with_redactions,
        "total_findings": total_findings,
        "clean_files": scanned - with_redactions,
    }


def result_record(relative_path: str, findings: list[dict]) -> dict:
    pages = sorted({item["page"] for item in findings if item.get("page") is not None})
    counts = Counter(item["type"] for item in findings)
    return {
        "filename": relative_path,
        "finding_count": len(findings),
        "pages": pages,
        "finding_types": dict(counts),
        "findings": findings,
    }
