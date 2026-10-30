from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from telethon.tl.functions.account import GetNotifySettingsRequest
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    Channel,
    ChatPhotoEmpty,
    DialogFilter,
    InputNotifyBroadcasts,
    InputPeerChannel,
    InputPeerUser,
    PeerNotifySettings,
    TextWithEntities,
)

from bot_allert import app as app_module
from bot_allert.app import HELP, Relay
from bot_allert.config import Settings
from bot_allert.state import load_folder

ALERTS_ID = -1000000000111
FUTURE = datetime.now(timezone.utc) + timedelta(hours=1)


def _folder(title, *peers):
    return DialogFilter(
        id=2,
        title=TextWithEntities(text=title, entities=[]),
        pinned_peers=[],
        include_peers=list(peers),
        exclude_peers=[],
    )


def _channel(channel_id, broadcast=True):
    return Channel(id=channel_id, title="c", photo=ChatPhotoEmpty(), date=None, broadcast=broadcast, access_hash=1)


class FakeUser:
    def __init__(self, filters, entities=(), peer_settings=None, default_settings=None, fail=False):
        self.filters = filters
        self.entities = list(entities)
        self.peer_settings = peer_settings or PeerNotifySettings()
        self.default_settings = default_settings or PeerNotifySettings()
        self.fail = fail

    async def __call__(self, request):
        if self.fail:
            raise ConnectionError("offline")
        if isinstance(request, GetDialogFiltersRequest):
            return SimpleNamespace(filters=self.filters)
        if isinstance(request, GetNotifySettingsRequest):
            return self.default_settings if isinstance(request.peer, InputNotifyBroadcasts) else self.peer_settings
        raise AssertionError(request)

    async def get_entity(self, peers):
        return self.entities


class FakeEvent:
    def __init__(self, text):
        self.raw_text = text
        self.replies = []

    async def reply(self, text):
        self.replies.append(text)


@pytest.fixture
def relay(tmp_path):
    settings = Settings(
        api_id=1,
        api_hash="h",
        bot_token="t",
        user_session="",
        state_path=Path(tmp_path / "state.json"),
        folder_refresh_seconds=600,
    )
    return Relay(settings)


def _alerts_user(**kwargs):
    folder = _folder("Тревоги", InputPeerChannel(channel_id=111, access_hash=1))
    return FakeUser([folder], entities=[_channel(111)], **kwargs)


async def _command(relay, text):
    event = FakeEvent(text)
    await relay.on_command(event)
    return event.replies[-1]


async def test_folder_command_saves_real_title_and_reports_channel_count(relay):
    relay.user = _alerts_user()

    reply = await _command(relay, "/folder  тревоги ")

    assert reply == "Готово: слежу за папкой «Тревоги», каналов: 1."
    assert relay.channels == {ALERTS_ID}
    assert load_folder(relay.settings.state_path) == "Тревоги"


async def test_unknown_folder_lists_titles_and_keeps_state(relay):
    relay.user = _alerts_user()

    reply = await _command(relay, "/folder Нет такой")

    assert "не найдена" in reply and "Тревоги" in reply
    assert relay.folder is None and load_folder(relay.settings.state_path) is None


async def test_folder_with_only_supergroups_and_users_has_no_channels(relay):
    folder = _folder(
        "Чаты", InputPeerChannel(channel_id=222, access_hash=1), InputPeerUser(user_id=7, access_hash=1)
    )
    relay.user = FakeUser([folder], entities=[_channel(222, broadcast=False)])

    reply = await _command(relay, "/folder Чаты")

    assert "нет каналов" in reply
    assert relay.folder is None and relay.channels == set()


async def test_telegram_error_during_command_gets_a_reply(relay):
    relay.user = FakeUser([], fail=True)

    assert "попробуйте ещё раз" in await _command(relay, "/folder Тревоги")


async def test_unknown_text_gets_help(relay):
    assert await _command(relay, "привет") == HELP


async def test_restart_restores_folder_and_status_reports_missing_folder(relay):
    relay.user = _alerts_user()
    await _command(relay, "/folder Тревоги")
    restarted = Relay(relay.settings)
    restarted.user = relay.user
    restarted.folder = load_folder(relay.settings.state_path)

    await restarted.refresh()
    assert restarted.channels == {ALERTS_ID}

    restarted.user.filters = []
    await restarted.refresh()
    assert restarted.channels == {ALERTS_ID}
    assert "больше не найдена" in await _command(restarted, "/status")


@pytest.mark.parametrize(
    ("peer", "default", "silent"),
    [
        (PeerNotifySettings(mute_until=FUTURE), None, True),
        (PeerNotifySettings(), PeerNotifySettings(mute_until=FUTURE), True),
        (PeerNotifySettings(), None, False),
    ],
)
async def test_post_is_relayed_with_mute_from_owner_settings(relay, monkeypatch, peer, default, silent):
    relay.user = _alerts_user(peer_settings=peer, default_settings=default)
    relay.owner_id = 42
    sent = []

    async def fake_relay_post(user, bot, owner_id, message, title, silent):
        sent.append((owner_id, message, title, silent))

    monkeypatch.setattr(app_module, "relay_post", fake_relay_post)
    message = object()

    async def get_chat():
        return SimpleNamespace(title="Тревоги Киев")

    async def get_input_chat():
        return InputPeerChannel(channel_id=111, access_hash=1)

    event = SimpleNamespace(
        id=1, chat_id=ALERTS_ID, message=message, get_chat=get_chat, get_input_chat=get_input_chat
    )

    await relay.on_post(event)

    assert sent == [(42, message, "Тревоги Киев", silent)]
