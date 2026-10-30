import os

from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> None:
    api_id = int(os.environ.get("API_ID") or input("API_ID: "))
    api_hash = os.environ.get("API_HASH") or input("API_HASH: ")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = client.get_me()
        print(f"\nLogged in as {me.first_name} (id {me.id}). Put this into .env as USER_SESSION:\n")
        print(client.session.save())


if __name__ == "__main__":
    main()
