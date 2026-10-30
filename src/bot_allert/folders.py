from telethon import utils
from telethon.tl.types import DialogFilter, DialogFilterChatlist, InputPeerChannel

FOLDER_TYPES = (DialogFilter, DialogFilterChatlist)


def folder_title(folder) -> str:
    # Older layers send a plain str, newer ones TextWithEntities.
    return getattr(folder.title, "text", folder.title)


def folder_titles(filters) -> list[str]:
    return [folder_title(f) for f in filters if isinstance(f, FOLDER_TYPES)]


def find_folder(filters, name: str):
    wanted = name.strip().casefold()
    for folder in filters:
        if isinstance(folder, FOLDER_TYPES) and folder_title(folder).strip().casefold() == wanted:
            return folder
    return None


def channel_peers(folder) -> list[InputPeerChannel]:
    # Supergroups are InputPeerChannel too; broadcast_ids() tells them apart once resolved.
    return [p for p in [*folder.include_peers, *folder.pinned_peers] if isinstance(p, InputPeerChannel)]


def broadcast_ids(entities) -> set[int]:
    return {utils.get_peer_id(e) for e in entities if getattr(e, "broadcast", False)}
