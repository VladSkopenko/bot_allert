import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_folder(path: Path) -> str | None:
    try:
        folder = json.loads(path.read_text(encoding="utf-8")).get("folder")
    except FileNotFoundError:
        return None
    except (ValueError, AttributeError):
        log.warning("State file %s is unreadable, starting without a folder", path)
        return None
    return folder if isinstance(folder, str) and folder.strip() else None


def save_folder(path: Path, folder: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"folder": folder}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
