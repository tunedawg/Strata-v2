import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from .config import DATASETS_DIR, METADATA_FILE, SUPPORTED_EXTENSIONS, ensure_directories


@dataclass
class DatasetSummary:
    name: str
    indexed: bool
    file_count: int
    updated_at: str | None


def _load_state() -> dict:
    ensure_directories()
    if METADATA_FILE.exists():
        try:
            return json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"datasets": {}}
    return {"datasets": {}}


def _save_state(state: dict) -> None:
    ensure_directories()
    METADATA_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def sanitize_dataset_name(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|]+', "_", name).strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean[:120]


def dataset_dir(name: str) -> Path:
    return DATASETS_DIR / name


def index_file(name: str) -> Path:
    return dataset_dir(name) / "_index.json"


def manifest_file(name: str) -> Path:
    return dataset_dir(name) / "_manifest.json"


def create_dataset(name: str) -> str:
    ensure_directories()
    safe_name = sanitize_dataset_name(name)
    if not safe_name:
        raise ValueError("Dataset name is required.")
    path = dataset_dir(safe_name)
    if path.exists():
        raise ValueError("Dataset already exists.")
    path.mkdir(parents=True, exist_ok=False)
    state = _load_state()
    state.setdefault("datasets", {})[safe_name] = {"created_at": _utc_now(), "updated_at": _utc_now()}
    _save_state(state)
    return safe_name


def delete_dataset(name: str) -> None:
    path = dataset_dir(name)
    if not path.exists():
        raise FileNotFoundError("Dataset not found.")
    shutil.rmtree(path)
    state = _load_state()
    state.get("datasets", {}).pop(name, None)
    _save_state(state)


def touch_dataset(name: str) -> None:
    state = _load_state()
    state.setdefault("datasets", {}).setdefault(name, {})
    state["datasets"][name]["updated_at"] = _utc_now()
    _save_state(state)


def save_manifest(name: str, manifest: dict) -> None:
    manifest_file(name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    touch_dataset(name)


def load_manifest(name: str) -> dict:
    path = manifest_file(name)
    if not path.exists():
        return {"files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def list_dataset_files(name: str) -> list[Path]:
    root = dataset_dir(name)
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and not path.name.startswith("_") and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def list_datasets() -> list[DatasetSummary]:
    ensure_directories()
    state = _load_state()
    summaries: list[DatasetSummary] = []
    known_names = sorted({p.name for p in DATASETS_DIR.iterdir() if p.is_dir()} | set(state.get("datasets", {}).keys()))
    for name in known_names:
        root = dataset_dir(name)
        if not root.exists():
            continue
        metadata = state.get("datasets", {}).get(name, {})
        summaries.append(
            DatasetSummary(
                name=name,
                indexed=index_file(name).exists(),
                file_count=len(list_dataset_files(name)),
                updated_at=metadata.get("updated_at"),
            )
        )
    return summaries


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
