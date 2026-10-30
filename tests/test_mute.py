from datetime import datetime, timedelta, timezone

from telethon.tl.types import NotificationSoundNone, PeerNotifySettings

from bot_allert.mute import is_muted

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(hours=1)
PAST = NOW - timedelta(hours=1)


def test_mute_until_in_future_is_muted():
    assert is_muted(PeerNotifySettings(mute_until=FUTURE), None, NOW) is True


def test_expired_mute_is_not_muted_even_if_default_is_muted():
    default = PeerNotifySettings(mute_until=FUTURE)

    assert is_muted(PeerNotifySettings(mute_until=PAST), default, NOW) is False


def test_silent_channel_is_muted():
    assert is_muted(PeerNotifySettings(silent=True), None, NOW) is True


def test_silent_wins_over_expired_mute():
    assert is_muted(PeerNotifySettings(silent=True, mute_until=PAST), None, NOW) is True


def test_channel_without_own_setting_falls_back_to_broadcast_default():
    assert is_muted(PeerNotifySettings(), PeerNotifySettings(mute_until=FUTURE), NOW) is True
    assert is_muted(PeerNotifySettings(), PeerNotifySettings(silent=True), NOW) is True
    assert is_muted(PeerNotifySettings(), PeerNotifySettings(), NOW) is False


def test_no_settings_at_all_means_sound():
    assert is_muted(None, None, NOW) is False


def test_explicit_unmute_wins_over_muted_default():
    assert is_muted(PeerNotifySettings(silent=False), PeerNotifySettings(mute_until=FUTURE), NOW) is False


def test_sound_set_to_none_is_muted():
    assert is_muted(PeerNotifySettings(other_sound=NotificationSoundNone()), None, NOW) is True
    assert is_muted(PeerNotifySettings(), PeerNotifySettings(ios_sound=NotificationSoundNone()), NOW) is True
