import asyncio
import logging
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetNotifySettingsRequest
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import InputNotifyBroadcasts, InputNotifyPeer

from bot_allert.config import Settings
from bot_allert.folders import broadcast_ids, channel_peers, find_folder, folder_title, folder_titles
from bot_allert.mute import is_muted
from bot_allert.relay import relay_post
from bot_allert.state import load_folder, save_folder

log = logging.getLogger(__name__)

HELP = (
    "Я пересылаю сюда посты из каналов одной вашей папки Telegram.\n\n"
    "/folder <название> — выбрать папку\n"
    "/status — текущая папка и число каналов\n\n"
    "Если канал у вас замьючен, пост придёт без звука."
)


class Relay:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.user = TelegramClient(StringSession(settings.user_session), settings.api_id, settings.api_hash)
        self.bot = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
        self.owner_id: int | None = None
        self.folder: str | None = None
        self.folder_missing = False
        self.channels: set[int] = set()

    async def _filters(self):
        result = await self.user(GetDialogFiltersRequest())
        return getattr(result, "filters", result)

    async def _resolve_channels(self, folder) -> set[int]:
        # Resolving also caches access hashes, so posts from these channels can be handled after a restart.
        peers = channel_peers(folder)
        return broadcast_ids(await self.user.get_entity(peers)) if peers else set()

    async def refresh(self) -> None:
        if self.folder is None:
            return
        folder = find_folder(await self._filters(), self.folder)
        self.folder_missing = folder is None
        if folder is None:
            log.warning("Folder %r not found, keeping %d known channels", self.folder, len(self.channels))
            return
        self.channels = await self._resolve_channels(folder)
        log.info("Folder %r: %d channels", self.folder, len(self.channels))

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.folder_refresh_seconds)
            try:
                await self.refresh()
            except Exception:
                log.exception("Folder refresh failed")

    async def on_command(self, event) -> None:
        command, _, arg = (event.raw_text or "").strip().partition(" ")
        command = command.split("@")[0].lower()
        try:
            if command == "/folder":
                reply = await self._select_folder(arg.strip())
            elif command == "/status":
                reply = self._status()
            else:
                reply = HELP
        except Exception:
            log.exception("Command %r failed", command)
            reply = "Не получилось связаться с Telegram, попробуйте ещё раз через минуту."
        await event.reply(reply)

    def _status(self) -> str:
        if self.folder is None:
            return "Папка не выбрана. Отправьте /folder <название>."
        if self.folder_missing:
            return f"Папка «{self.folder}» больше не найдена. Выберите папку заново: /folder <название>."
        return f"Папка «{self.folder}», каналов: {len(self.channels)}."

    async def _select_folder(self, name: str) -> str:
        filters = await self._filters()
        titles = ", ".join(folder_titles(filters)) or "нет папок"
        if not name:
            return f"Укажите название: /folder <название>.\nВаши папки: {titles}"
        folder = find_folder(filters, name)
        if folder is None:
            return f"Папка «{name}» не найдена.\nВаши папки: {titles}"
        title = folder_title(folder)
        ids = await self._resolve_channels(folder)
        if not ids:
            return f"В папке «{title}» нет каналов. Добавьте каналы в папку вручную, не через правила."
        self.folder, self.channels, self.folder_missing = title, ids, False
        save_folder(self.settings.state_path, title)
        return f"Готово: слежу за папкой «{title}», каналов: {len(ids)}."

    async def on_post(self, event) -> None:
        try:
            chat = await event.get_chat()
            peer, default = await asyncio.gather(
                self.user(GetNotifySettingsRequest(InputNotifyPeer(await event.get_input_chat()))),
                self.user(GetNotifySettingsRequest(InputNotifyBroadcasts())),
            )
            silent = is_muted(peer, default, datetime.now(timezone.utc))
            await relay_post(self.user, self.bot, self.owner_id, event.message, chat.title, silent)
        except Exception:
            log.exception("Relay failed for post %s in %s", event.id, event.chat_id)

    async def run(self) -> None:
        await self.user.connect()
        if not await self.user.is_user_authorized():
            raise SystemExit("USER_SESSION is not authorized, run: python -m bot_allert.login")
        await self.bot.start(bot_token=self.settings.bot_token)
        self.owner_id = (await self.user.get_me()).id

        self.folder = load_folder(self.settings.state_path)
        if self.folder is None:
            log.info("No folder selected yet, waiting for /folder")
        try:
            await self.refresh()
        except Exception:
            log.exception("Initial folder refresh failed, retrying in %ss", self.settings.folder_refresh_seconds)

        self.bot.add_event_handler(
            self.on_command,
            events.NewMessage(func=lambda e: e.is_private and e.sender_id == self.owner_id),
        )
        self.user.add_event_handler(self.on_post, events.NewMessage(func=lambda e: e.chat_id in self.channels))

        tasks = [
            asyncio.create_task(self.user.run_until_disconnected()),
            asyncio.create_task(self.bot.run_until_disconnected()),
            asyncio.create_task(self._refresh_loop()),
        ]
        # If either client stops (e.g. the session was terminated), exit so Docker restarts the process.
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
        raise SystemExit("A Telegram client disconnected")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    settings.state_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(Relay(settings).run())
