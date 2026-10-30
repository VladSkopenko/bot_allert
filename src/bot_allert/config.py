import os
from dataclasses import dataclass
from pathlib import Path

MIN_REFRESH_SECONDS = 60


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Environment variable {name} is required (see .env.example)")
    return value


def _int(name: str, raw: str, minimum: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"Environment variable {name} must be an integer, got {raw!r}") from None
    if value < minimum:
        raise SystemExit(f"Environment variable {name} must be >= {minimum}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    user_session: str
    state_path: Path
    folder_refresh_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_id=_int("API_ID", _required("API_ID"), 1),
            api_hash=_required("API_HASH"),
            bot_token=_required("BOT_TOKEN"),
            user_session=_required("USER_SESSION"),
            state_path=Path(os.environ.get("STATE_PATH", "data/state.json")),
            folder_refresh_seconds=_int(
                "FOLDER_REFRESH_SECONDS", os.environ.get("FOLDER_REFRESH_SECONDS", "600"), MIN_REFRESH_SECONDS
            ),
        )
