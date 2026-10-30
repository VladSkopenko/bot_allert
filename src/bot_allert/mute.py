from datetime import datetime

from telethon.tl.types import NotificationSoundNone

SOUND_FIELDS = ("other_sound", "ios_sound", "android_sound")


def _own_decision(settings, now: datetime) -> bool | None:
    if settings is None:
        return None
    # Official apps implement "disable sound" as a NotificationSoundNone sound.
    if settings.silent or any(isinstance(getattr(settings, f), NotificationSoundNone) for f in SOUND_FIELDS):
        return True
    if settings.mute_until is not None:
        return settings.mute_until > now
    if settings.silent is False:
        return False
    return None


def is_muted(peer_settings, default_settings, now: datetime) -> bool:
    decision = _own_decision(peer_settings, now)
    if decision is None:
        decision = _own_decision(default_settings, now)
    return bool(decision)
