import copy
import io
import logging

from telethon import utils
from telethon.tl.types import MessageEntityBold, MessageMediaWebPage

log = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
ATTACHMENT_FAILED = "\n\n(вложение не удалось переслать)"


def utf16_len(text: str) -> int:
    # Telegram entity offsets are counted in UTF-16 code units, not Python chars.
    return len(text.encode("utf-16-le")) // 2


def build_text(title: str, body: str, entities) -> tuple[str, list]:
    header = f"{title}\n" if body else title
    shift = utf16_len(header)
    shifted = []
    for entity in entities or []:
        moved = copy.copy(entity)
        moved.offset += shift
        shifted.append(moved)
    return header + body, [MessageEntityBold(offset=0, length=utf16_len(title)), *shifted]


def fit(text: str, entities: list, limit: int) -> tuple[str, list]:
    if utf16_len(text) <= limit:
        return text, entities
    cut = text.encode("utf-16-le")[: (limit - 1) * 2].decode("utf-16-le", errors="ignore")
    size = utf16_len(cut)
    clipped = []
    for entity in entities:
        if entity.offset < size:
            entity = copy.copy(entity)
            entity.length = min(entity.length, size - entity.offset)
            clipped.append(entity)
    return cut + "…", clipped


async def send_text(bot, owner_id: int, text: str, entities: list, silent: bool) -> None:
    text, entities = fit(text, entities, TEXT_LIMIT)
    try:
        await bot.send_message(owner_id, text, formatting_entities=entities, silent=silent)
    except Exception:
        # Channel entities a bot may not send (mention-name, custom emoji): keep only the bold title.
        log.exception("Send with original formatting failed, retrying with the title only")
        await bot.send_message(owner_id, text, formatting_entities=entities[:1], silent=silent)


async def _download(user, message) -> io.BytesIO:
    data = await user.download_media(message, file=bytes)
    if not data:
        raise RuntimeError("empty download")
    buf = io.BytesIO(data)
    buf.name = message.file.name or f"file{message.file.ext or ''}"
    return buf


async def relay_post(user, bot, owner_id: int, message, title: str, silent: bool) -> None:
    text, entities = build_text(title, message.message or "", message.entities)
    media = message.media
    # Polls, geo, dice etc. have no file to re-upload: their text is all we can relay.
    if media is None or isinstance(media, MessageMediaWebPage) or message.file is None:
        await send_text(bot, owner_id, text, entities, silent)
        return

    text_sent = False
    try:
        buf = await _download(user, message)
        file_kwargs = {
            "attributes": getattr(message.document, "attributes", None),
            "mime_type": message.file.mime_type,
            # Without this an image sent as a file comes back as a compressed photo.
            "force_document": message.document is not None and utils.is_image(buf.name),
            "silent": silent,
        }
        if utf16_len(text) <= CAPTION_LIMIT:
            await bot.send_file(owner_id, buf, caption=text, formatting_entities=entities, **file_kwargs)
            return
        await send_text(bot, owner_id, text, entities, silent)
        text_sent = True
        await bot.send_file(owner_id, buf, **file_kwargs)
    except Exception:
        log.exception("Attachment relay failed")
        if text_sent:
            await send_text(bot, owner_id, *build_text(title, ATTACHMENT_FAILED.strip(), None), silent)
        else:
            await send_text(bot, owner_id, text + ATTACHMENT_FAILED, entities, silent)
