import pytest

from bot_allert.config import Settings

BASE = {"API_ID": "1", "API_HASH": "h", "BOT_TOKEN": "t", "USER_SESSION": "s"}


@pytest.fixture
def env(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_defaults(env):
    settings = Settings.from_env()

    assert settings.folder_refresh_seconds == 600
    assert str(settings.state_path) == "data/state.json"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("API_ID", "abc", "must be an integer"),
        ("FOLDER_REFRESH_SECONDS", "0", "must be >= 60"),
        ("BOT_TOKEN", "", "is required"),
    ],
)
def test_invalid_values_exit_with_hint(env, key, value, message):
    env.setenv(key, value)

    with pytest.raises(SystemExit, match=message):
        Settings.from_env()
