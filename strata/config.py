import os
import tempfile
from pathlib import Path


APP_NAME = "Strata"
DEFAULT_DATA_ROOT = Path.home() / "Documents" / APP_NAME


def resolve_data_root() -> Path:
    override = os.environ.get("STRATA_DATA_ROOT")
    if override:
        return Path(override)
    candidates = [
        DEFAULT_DATA_ROOT,
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME,
        Path(tempfile.gettempdir()) / APP_NAME,
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    return DEFAULT_DATA_ROOT


DATA_ROOT = resolve_data_root()
DATASETS_DIR = DATA_ROOT / "datasets"
EXPORTS_DIR = DATA_ROOT / "exports"
LOGS_DIR = DATA_ROOT / "logs"
CACHE_DIR = DATA_ROOT / "cache"
INDEX_CACHE_DIR = CACHE_DIR / "indexes"
METADATA_FILE = DATA_ROOT / "strata_state.json"
PORT = int(os.environ.get("STRATA_PORT", "18888"))

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"
TEMPLATES_DIR = REPO_ROOT / "templates"
ASSETS_DIR = REPO_ROOT / "assets"
TOOLS_DIR = REPO_ROOT / "tools"

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".csv",
    ".xlsx",
    ".xls",
    ".txt",
    ".md",
    ".rtf",
    ".eml",
    ".msg",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
}


def ensure_directories() -> None:
    for path in (DATA_ROOT, DATASETS_DIR, EXPORTS_DIR, LOGS_DIR, CACHE_DIR, INDEX_CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
