# bot_allert

**English** · [Українська](README.uk.md)

A self-hosted Telegram bot that collects new posts from the channels in one of your Telegram folders and sends them to you in a single chat. Posts from channels you have muted arrive silently. Posts from the other channels arrive with sound.

It was made for air-raid alert channels: you follow a dozen of them, put them in one folder, and get one feed where the important ones ring and the rest don't.

Each person runs their own copy for their own account. Nothing is shared and there is no central server.

## How it works

One process runs two Telegram clients:

- a **userbot** logged in as you. It only reads: your folders, your per-channel notification settings and new posts in those channels. It never posts, marks as read, joins or leaves anything;
- a regular **bot** that sends the posts to you.

For every new post the userbot checks whether that channel is muted in your Telegram right now. The bot then re-sends the post (text with formatting, photos, files) with or without sound accordingly. Changing a channel's mute setting takes effect on the next post, with no restart.

## What you need

- a Telegram account;
- a machine that stays on: a VPS, a home server, or your laptop for testing. The [free Oracle Cloud VM](#free-hosting-on-oracle-cloud) below is enough;
- [Docker](https://docs.docker.com/get-docker/), or Python 3.12+ with [uv](https://docs.astral.sh/uv/).

## Setup

### 1. Get the credentials

1. **API_ID and API_HASH.** Log in to <https://my.telegram.org> with your account, open **API development tools** and create an app. Any name and platform will do.
2. **BOT_TOKEN.** In Telegram open [@BotFather](https://t.me/BotFather), send `/newbot` and follow the steps.

### 2. Configure

```bash
git clone https://github.com/VladSkopenko/bot_allert.git
cd bot_allert
cp .env.example .env
```

Open `.env` and fill in `API_ID`, `API_HASH` and `BOT_TOKEN`.

### 3. Log in as yourself (once)

```bash
docker compose run --rm bot python -m bot_allert.login
# or without Docker:
uv run --env-file .env python -m bot_allert.login
```

It asks for your phone number, the code Telegram sends you, and your 2FA password if you have one. Then it prints a long string. Put it into `.env` as `USER_SESSION`.

> [!WARNING]
> `USER_SESSION` gives full access to your Telegram account. Never share it or commit `.env` (it is already in `.gitignore`). If it leaks, end the session in Telegram → Settings → Devices.

### 4. Start the bot chat

From your account, open your new bot and press **Start**. A bot cannot message someone who has never started it.

### 5. Run

```bash
docker compose up -d --build
docker compose logs -f bot
```

Without Docker:

```bash
uv run --env-file .env python -m bot_allert
```

## Usage

1. In Telegram create a folder (Settings → Chat Folders) and add the channels to it **by hand**.
2. Send the bot `/folder <folder name>`, for example `/folder Alerts`.
3. Mute in Telegram the channels whose posts you want to receive silently.

| Command | What it does |
|---|---|
| `/folder <name>` | Select the folder to follow. The choice is saved and survives restarts. |
| `/status` | Show the current folder and how many channels it has. |
| `/start` | Show help. |

The bot answers only you (the account from `USER_SESSION`) and ignores everyone else. Its replies are in Russian.

Notes:

- Only channels **added to the folder by hand** count. Rule-based folders such as "all channels" are not supported. Groups and private chats in the folder are skipped.
- Folder changes are picked up every `FOLDER_REFRESH_SECONDS` (10 minutes by default), or right away when you send `/folder` again.
- Don't mute the chat with the bot itself, or every post will arrive silently.

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_ID` | yes | | From my.telegram.org |
| `API_HASH` | yes | | From my.telegram.org |
| `BOT_TOKEN` | yes | | From @BotFather |
| `USER_SESSION` | yes | | Output of `python -m bot_allert.login` |
| `STATE_PATH` | no | `data/state.json` | Where the selected folder is stored |
| `FOLDER_REFRESH_SECONDS` | no | `600` | How often to re-read the folder, at least 60 |

## Free hosting on Oracle Cloud

The bot needs very little (about 100 MB of RAM) and no open ports, so Oracle Cloud's Always Free tier can run it for free.

1. **Create the VM.** In the Oracle Cloud console go to **Compute → Instances → Create instance**.
   - Image: **Canonical Ubuntu 24.04**.
   - Shape: **VM.Standard.E2.1.Micro** (under *Specialty and previous generation*) or **VM.Standard.A1.Flex**. Both are marked *Always Free-eligible*. A1 is often "Out of capacity". In that case use E2.1.Micro in the availability domain where Oracle says it is available.
   - Networking: **Create new virtual cloud network** and **Create new public subnet**.
   - SSH keys: upload your public key, for example one created with `ssh-keygen -t ed25519 -f ~/.ssh/oracle_bot`.
2. **Give it a public IP** if it didn't get one: instance → **Networking** → the VNIC → **IP administration** → ⋮ → **Edit** → **Ephemeral public IP**.
3. **Install Docker**, and add swap so the image builds on 1 GB of RAM:
   ```bash
   ssh -i ~/.ssh/oracle_bot ubuntu@<IP>
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   exit
   ```
4. **Copy the project and start it.** Run this on your computer, inside the project folder with a filled `.env`:
   ```bash
   rsync -az -e "ssh -i ~/.ssh/oracle_bot" --exclude .venv --exclude data ./ ubuntu@<IP>:~/bot_allert/
   ssh -i ~/.ssh/oracle_bot ubuntu@<IP> 'cd bot_allert && chmod 600 .env && docker compose up -d --build'
   ```

To update later, repeat step 4. `data/` is excluded so the selected folder on the server is kept.

> [!IMPORTANT]
> Run only one copy of the bot at a time. Two copies with the same session and bot token deliver every post twice.

## Limitations

- Posts published while the bot is down (for example during a restart) are not delivered afterwards.
- Albums arrive as separate messages.
- Edits and deletions of posts are not mirrored.

More in [docs/known-limitations.md](docs/known-limitations.md). The original design spec is in [docs/spec.md](docs/spec.md).

## Development

```bash
uv sync
uv run pytest -q
```

Code layout:

| Path | Purpose |
|---|---|
| `src/bot_allert/app.py` | Wires the two clients, commands and the post handler |
| `src/bot_allert/relay.py` | Re-sends a post: header, formatting, media |
| `src/bot_allert/mute.py` | Decides whether a channel is muted |
| `src/bot_allert/folders.py` | Finds the folder and its channels |
| `src/bot_allert/login.py` | One-off login that prints `USER_SESSION` |

## License

[MIT](LICENSE)
