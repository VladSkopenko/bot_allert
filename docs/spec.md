---
title: 'Air-alert folder relay bot'
type: 'feature'
created: '2026-10-30'
status: 'done'
baseline_commit: 'NO_VCS'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The owner (one person) follows ~20 air-alert channels and has to watch each one separately.

**Approach:** One process with two Telethon clients: a userbot logged in as the owner (StringSession, consented) and a regular bot. The owner tells the bot a Telegram folder name; the userbot takes the channels explicitly listed in that folder, listens to their new posts, and the bot re-sends each post to the owner — silently if that channel is muted in the owner's Telegram, with sound otherwise.

## Boundaries & Constraints

**Always:** Owner = `user.get_me().id`; the bot ignores messages from anyone else. Mute is read live from the owner's Telegram on every post (per-channel `mute_until`/`silent`, falling back to the broadcast default when the channel has no own setting). A failure on one post is logged and never stops the listener. Tunables (state path, folder refresh interval) come from env with defaults. Bot replies in Russian.

**Ask First:** Supporting more than one owner; adding any storage beyond the single JSON state file.

**Never:** Writing to the owner's account (no reads-marking, no forwarding from the userbot, no joining/leaving channels). Rule-based folder contents (`broadcasts`/`groups` flags) — only explicitly listed peers. Album grouping, edits/deletions of posts, web UI.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Set folder | owner sends `/folder Тревоги` | folder matched by title (case-insensitive, trimmed), saved to state, reply with channel count | N/A |
| Unknown folder | `/folder Нет такой` | reply listing existing folder titles; state unchanged | N/A |
| Folder without channels | folder has only groups/users or is rule-based | reply "в папке нет каналов"; state unchanged | N/A |
| Post in unmuted channel | text post | bot sends `<b>Channel</b>\n<text>` with original formatting, with sound | N/A |
| Post in muted channel | `mute_until` in future or `silent=True` | same message, `silent=True` | N/A |
| Mute expired | `mute_until` in the past | sent with sound | N/A |
| Photo/document post | media + caption ≤1024 | media re-uploaded by bot with header+caption | download/send error → log, send text-only with "(вложение не удалось переслать)" |
| Long caption | media + text >1024 | text message first, then media without caption, same silent flag | N/A |
| Link preview only | `MessageMediaWebPage` | sent as plain text | N/A |
| Stranger writes bot | any message from non-owner | ignored | N/A |
| Restart | state file has folder | folder re-resolved on start, relaying resumes | folder gone → log, wait for `/folder` |

</frozen-after-approval>

## Code Map

- `src/bot_allert/config.py` -- env settings (API_ID, API_HASH, BOT_TOKEN, USER_SESSION, STATE_PATH, FOLDER_REFRESH_SECONDS)
- `src/bot_allert/state.py` -- load/save `{"folder": str|null}` JSON
- `src/bot_allert/folders.py` -- pure: pick filter by title, list titles, channel peers, keep broadcast (non-supergroup) ids
- `src/bot_allert/mute.py` -- pure: `is_muted(peer_settings, default_settings, now)`
- `src/bot_allert/relay.py` -- pure: build header+text+shifted entities, caption split; async `relay_post`
- `src/bot_allert/app.py` -- wires clients, handlers, periodic folder refresh
- `src/bot_allert/login.py` -- one-off interactive login, prints StringSession

## Tasks & Acceptance

**Execution:**
- [x] `tests/test_folders.py`, `tests/test_mute.py`, `tests/test_relay.py`, `tests/test_state.py` -- failing tests for every matrix row reachable without network (real `telethon.tl.types` objects, fake clients for `relay_post`) -- TDD first
- [x] `pyproject.toml` -- uv project, Python 3.12, `telethon`, dev `pytest`, `pytest-asyncio`
- [x] `src/bot_allert/{config,state,folders,mute,relay}.py` -- implement to green
- [x] `src/bot_allert/app.py` + `__main__.py` -- `python -m bot_allert`; commands `/start` (help), `/folder <name>`, `/status`; refresh channel set every `FOLDER_REFRESH_SECONDS` (default 600)
- [x] `src/bot_allert/login.py` -- `python -m bot_allert.login` asks phone/code/2FA, prints session string
- [x] `Dockerfile`, `docker-compose.yml` (`restart: unless-stopped`, `./data` volume, `env_file: .env`), `.env.example`, `.gitignore`, `.dockerignore`, `README.md` (setup: my.telegram.org app, BotFather token, login, owner presses /start, compose up)

**Acceptance Criteria:**
- Given a valid `.env`, when `docker compose up -d` runs, then the process connects both clients and logs the resolved folder (or that none is set).
- Given the owner never pressed `/start` on the bot, when a post arrives, then the send error is logged and the listener keeps running.

## Design Notes

Title of a `DialogFilter` is `str` in older layers and `TextWithEntities` in newer — read `.text` when present. Peers = `include_peers + pinned_peers`, keep `InputPeerChannel`, store marked ids (`utils.get_peer_id(PeerChannel(id))`) to compare with `event.chat_id`.

The bot cannot forward from channels it is not in, so posts are re-sent: the userbot downloads media to memory, the bot uploads it. Header entity offsets are in UTF-16 units:

```python
shift = len(header.encode("utf-16-le")) // 2
moved = copy.copy(entity); moved.offset += shift  # TLObjects are not dataclasses; never mutate the event
```

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all green
- `docker build -t bot_allert .` -- expected: image builds

**Manual checks (if no CLI):**
- Owner sends `/folder <name>`, posts in a muted channel arrive silently and in an unmuted one with sound.

## Suggested Review Order

**Post flow**

- Entry point: mute read live per post, then re-send through the bot.
  [`app.py:103`](../src/bot_allert/app.py#L103)

- Re-upload media; long caption sends text first, no duplicate on failure.
  [`relay.py:64`](../src/bot_allert/relay.py#L64)

- Retry with only the bold title if channel entities are rejected.
  [`relay.py:45`](../src/bot_allert/relay.py#L45)

- Title header with UTF-16 entity shift; truncation to 4096.
  [`relay.py:20`](../src/bot_allert/relay.py#L20)

- Mute rules: silent, sound=None, mute_until, then broadcast default.
  [`mute.py:8`](../src/bot_allert/mute.py#L8)

**Folder selection**

- Saves the real folder title; resolves peers to drop supergroups.
  [`app.py:87`](../src/bot_allert/app.py#L87)

- Resolving entities also caches access hashes across restarts.
  [`app.py:41`](../src/bot_allert/app.py#L41)

- Supergroups share InputPeerChannel; broadcast flag separates them.
  [`folders.py:24`](../src/bot_allert/folders.py#L24)

**Lifecycle**

- Exit when either client stops so Docker restarts the process.
  [`app.py:142`](../src/bot_allert/app.py#L142)

- /status tells the owner when the folder disappeared.
  [`app.py:80`](../src/bot_allert/app.py#L80)

**Peripherals**

- Env validation with friendly exits; refresh interval >= 60.
  [`config.py:15`](../src/bot_allert/config.py#L15)

- Tests for app, relay, mute, folders, state, config.
  [`test_app.py`](../tests/test_app.py)
