from types import SimpleNamespace

import pytest
from telethon.tl.types import (
    DocumentAttributeVideo,
    MessageEntityBold,
    MessageEntityItalic,
    MessageEntityMentionName,
    MessageMediaWebPage,
    WebPageEmpty,
)

from bot_allert.relay import ATTACHMENT_FAILED, CAPTION_LIMIT, TEXT_LIMIT, build_text, relay_post, utf16_len

OWNER = 42


class FakeBot:
    def __init__(self, fail_file=False, reject_foreign_entities=False):
        self.calls = []
        self.fail_file = fail_file
        self.reject_foreign_entities = reject_foreign_entities

    async def send_message(self, entity, message, **kwargs):
        if self.reject_foreign_entities and len(kwargs["formatting_entities"]) > 1:
            raise RuntimeError("entity rejected")
        self.calls.append(("message", entity, message, kwargs))

    async def send_file(self, entity, file, **kwargs):
        if self.fail_file:
            raise RuntimeError("upload failed")
        self.calls.append(("file", entity, file, kwargs))


class FakeUser:
    def __init__(self, data=b"img", fail=False):
        self.data = data
        self.fail = fail

    async def download_media(self, message, file=None):
        if self.fail:
            raise RuntimeError("download failed")
        return self.data


def _post(text="", entities=None, media=None, name=None, ext=".jpg", mime="image/jpeg", document=None, has_file=True):
    return SimpleNamespace(
        message=text,
        entities=entities,
        media=media,
        file=SimpleNamespace(name=name, ext=ext, mime_type=mime) if media and has_file else None,
        document=document,
    )


def test_build_text_bolds_channel_title_and_shifts_original_entities():
    italic = MessageEntityItalic(offset=0, length=6)

    text, entities = build_text("Канал 🚨", "Тревога", [italic])

    assert text == "Канал 🚨\nТревога"
    assert entities[0] == MessageEntityBold(offset=0, length=8)
    # "Канал 🚨\n" is 9 UTF-16 units: the emoji counts as two
    assert entities[1].offset == 9 and entities[1].length == 6
    assert italic.offset == 0


def test_build_text_without_body_is_just_the_title():
    assert build_text("Канал", "", None) == ("Канал", [MessageEntityBold(offset=0, length=5)])


async def test_text_post_is_sent_with_requested_silence():
    bot = FakeBot()

    await relay_post(FakeUser(), bot, OWNER, _post("Отбой"), "Канал", silent=True)

    [(kind, entity, message, kwargs)] = bot.calls
    assert (kind, entity, message) == ("message", OWNER, "Канал\nОтбой")
    assert kwargs["silent"] is True


async def test_text_over_limit_is_truncated_with_clipped_entities():
    bot = FakeBot()
    body = "🚨" * TEXT_LIMIT
    italic = MessageEntityItalic(offset=0, length=utf16_len(body))

    await relay_post(FakeUser(), bot, OWNER, _post(body, [italic]), "Канал", silent=False)

    [(_, _, message, kwargs)] = bot.calls
    assert utf16_len(message) <= TEXT_LIMIT and message.endswith("…")
    assert all(e.offset + e.length <= utf16_len(message) for e in kwargs["formatting_entities"])


async def test_entities_bot_cannot_send_are_dropped_on_retry_keeping_bold_title():
    bot = FakeBot(reject_foreign_entities=True)
    mention = MessageEntityMentionName(offset=0, length=5, user_id=1)

    await relay_post(FakeUser(), bot, OWNER, _post("Отбой", [mention]), "Канал", silent=True)

    [(_, _, message, kwargs)] = bot.calls
    assert message == "Канал\nОтбой"
    assert kwargs["formatting_entities"] == [MessageEntityBold(offset=0, length=5)]
    assert kwargs["silent"] is True


async def test_link_preview_post_is_sent_as_text():
    bot = FakeBot()
    media = MessageMediaWebPage(webpage=WebPageEmpty(id=1))

    await relay_post(FakeUser(), bot, OWNER, _post("https://x", media=media), "Канал", silent=False)

    assert [c[0] for c in bot.calls] == ["message"]


async def test_media_without_file_like_poll_is_sent_as_plain_text():
    bot = FakeBot()

    await relay_post(FakeUser(), bot, OWNER, _post("Опрос", media=object(), has_file=False), "Канал", silent=False)

    [(kind, _, message, _)] = bot.calls
    assert (kind, message) == ("message", "Канал\nОпрос")


async def test_photo_is_reuploaded_with_caption_and_named_by_extension():
    bot = FakeBot()

    await relay_post(FakeUser(b"jpg"), bot, OWNER, _post("Ракета", media=object()), "Канал", silent=False)

    [(kind, entity, file, kwargs)] = bot.calls
    assert kind == "file"
    assert file.getvalue() == b"jpg" and file.name == "file.jpg"
    assert kwargs["caption"] == "Канал\nРакета"
    assert kwargs["silent"] is False
    assert kwargs["force_document"] is False


async def test_document_keeps_its_name_mime_and_attributes():
    bot = FakeBot()
    video = DocumentAttributeVideo(duration=3, w=10, h=10)
    post = _post(media=object(), name="clip.mp4", mime="video/mp4", document=SimpleNamespace(attributes=[video]))

    await relay_post(FakeUser(), bot, OWNER, post, "Канал", silent=False)

    [(_, _, file, kwargs)] = bot.calls
    assert file.name == "clip.mp4"
    assert kwargs["attributes"] == [video]
    assert kwargs["mime_type"] == "video/mp4"
    assert kwargs["force_document"] is False


async def test_image_sent_as_document_stays_a_document():
    bot = FakeBot()
    post = _post(media=object(), name="map.png", mime="image/png", document=SimpleNamespace(attributes=[]))

    await relay_post(FakeUser(), bot, OWNER, post, "Канал", silent=False)

    assert bot.calls[0][3]["force_document"] is True


async def test_long_caption_sends_text_first_then_bare_media_with_same_silence():
    bot = FakeBot()
    long_text = "а" * CAPTION_LIMIT

    await relay_post(FakeUser(), bot, OWNER, _post(long_text, media=object()), "Канал", silent=True)

    assert [c[0] for c in bot.calls] == ["message", "file"]
    assert "caption" not in bot.calls[1][3]
    assert all(c[3]["silent"] is True for c in bot.calls)


async def test_long_caption_upload_failure_does_not_repeat_the_text():
    bot = FakeBot(fail_file=True)
    long_text = "а" * CAPTION_LIMIT

    await relay_post(FakeUser(), bot, OWNER, _post(long_text, media=object()), "Канал", silent=True)

    assert [c[2] for c in bot.calls] == ["Канал\n" + long_text, "Канал\n" + ATTACHMENT_FAILED.strip()]
    assert all(c[3]["silent"] is True for c in bot.calls)


@pytest.mark.parametrize(
    ("user", "bot"),
    [(FakeUser(fail=True), FakeBot()), (FakeUser(data=None), FakeBot()), (FakeUser(), FakeBot(fail_file=True))],
)
async def test_attachment_failure_falls_back_to_text_with_note(user, bot):
    await relay_post(user, bot, OWNER, _post("Ракета", media=object()), "Канал", silent=True)

    [(kind, _, message, kwargs)] = bot.calls
    assert kind == "message"
    assert message == "Канал\nРакета" + ATTACHMENT_FAILED
    assert kwargs["silent"] is True
