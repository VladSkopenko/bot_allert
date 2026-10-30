from telethon.tl.types import (
    Channel,
    ChatPhotoEmpty,
    DialogFilter,
    DialogFilterChatlist,
    DialogFilterDefault,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
    TextWithEntities,
)

from bot_allert.folders import broadcast_ids, channel_peers, find_folder, folder_titles


def _folder(title, include=(), pinned=(), **flags):
    return DialogFilter(
        id=2,
        title=TextWithEntities(text=title, entities=[]),
        pinned_peers=list(pinned),
        include_peers=list(include),
        exclude_peers=[],
        **flags,
    )


def test_find_folder_matches_title_case_insensitive_and_trimmed():
    alerts = _folder("Тревоги")
    filters = [DialogFilterDefault(), _folder("Работа"), alerts]

    assert find_folder(filters, "  тревоги ") is alerts


def test_find_folder_supports_shared_chatlist_folders():
    shared = DialogFilterChatlist(
        id=3,
        title=TextWithEntities(text="Shared", entities=[]),
        pinned_peers=[],
        include_peers=[InputPeerChannel(channel_id=5, access_hash=1)],
    )

    assert find_folder([shared], "shared") is shared


def test_find_folder_returns_none_for_unknown_name():
    assert find_folder([_folder("Работа")], "Нет такой") is None


def test_find_folder_accepts_plain_string_title():
    legacy = _folder("x")
    legacy.title = "Old Layer"

    assert find_folder([legacy], "old layer") is legacy


def test_folder_titles_skips_default_folder():
    filters = [DialogFilterDefault(), _folder("Работа"), _folder("Тревоги")]

    assert folder_titles(filters) == ["Работа", "Тревоги"]


def _channel(channel_id, broadcast):
    return Channel(id=channel_id, title="c", photo=ChatPhotoEmpty(), date=None, broadcast=broadcast, access_hash=1)


def test_channel_peers_keeps_included_and_pinned_channel_peers_only():
    channel = InputPeerChannel(channel_id=111, access_hash=1)
    pinned = InputPeerChannel(channel_id=222, access_hash=1)
    folder = _folder(
        "Тревоги",
        include=[channel, InputPeerUser(user_id=7, access_hash=1), InputPeerChat(chat_id=8)],
        pinned=[pinned],
    )

    assert channel_peers(folder) == [channel, pinned]


def test_channel_peers_ignores_rule_based_flags():
    assert channel_peers(_folder("Все каналы", broadcasts=True)) == []


def test_broadcast_ids_drops_supergroups_and_returns_marked_ids():
    assert broadcast_ids([_channel(111, True), _channel(222, False)]) == {-1000000000111}
