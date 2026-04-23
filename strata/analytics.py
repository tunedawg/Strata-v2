import json
import os
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .config import DATA_ROOT


MIXPANEL_TOKEN = "d8dafeb70e4d1eaff78262d01e1d3b83"
DEVICE_ID_FILE = DATA_ROOT / ".device_id"


def analytics_enabled() -> bool:
    return os.environ.get("STRATA_DISABLE_ANALYTICS", "0") != "1"


def get_device_id() -> str:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    if DEVICE_ID_FILE.exists():
        return DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
    device_id = str(uuid.uuid4())
    DEVICE_ID_FILE.write_text(device_id, encoding="utf-8")
    return device_id


def track_event(event_name: str, properties: dict | None = None) -> None:
    if not analytics_enabled():
        return

    payload = {
        "event": event_name,
        "properties": {
            "token": MIXPANEL_TOKEN,
            "distinct_id": get_device_id(),
            "product": "Strata",
            **(properties or {}),
        },
    }

    def _send() -> None:
        try:
            body = urllib.parse.urlencode({"data": json.dumps(payload)}).encode("utf-8")
            request = urllib.request.Request("https://api.mixpanel.com/track", data=body, method="POST")
            urllib.request.urlopen(request, timeout=3)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
