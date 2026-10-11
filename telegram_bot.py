import asyncio
import os
from typing import Any

import httpx

from app.main import handle_message, init_db, remember_message, ROOT


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_IDS = {
    value.strip()
    for value in os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").split(",")
    if value.strip()
}
API = f"https://api.telegram.org/bot{TOKEN}"


async def telegram_call(client: httpx.AsyncClient, method: str, **payload: Any) -> Any:
    response = await client.post(f"{API}/{method}", json=payload)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(body)
    return body.get("result")


async def send_telegram(client: httpx.AsyncClient, chat_id: str, text: str) -> None:
    # Telegram text messages are limited to 4096 characters.
    for start in range(0, max(len(text), 1), 4000):
        await telegram_call(client, "sendMessage", chat_id=chat_id, text=text[start : start + 4000])


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not ROOT.is_dir():
        raise RuntimeError(f"CODEX_WORKSPACE does not exist: {ROOT}")
    init_db()
    offset = 0
    async with httpx.AsyncClient(timeout=65) as client:
        me = await telegram_call(client, "getMe")
        print(f"Telegram bot active: @{me['username']}")
        while True:
            try:
                updates = await telegram_call(
                    client,
                    "getUpdates",
                    offset=offset,
                    timeout=50,
                    allowed_updates=["message"],
                )
                for update in updates or []:
                    offset = max(offset, int(update["update_id"]) + 1)
                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    text = message.get("text", "").strip()
                    message_id = f"telegram:{update.get('update_id')}"
                    if not chat_id or not text or not remember_message(message_id):
                        continue
                    if chat_id not in ALLOWED_CHAT_IDS:
                        await send_telegram(
                            client,
                            chat_id,
                            "Bu Telegram chat ID yetkili değil. Chat ID: "
                            + chat_id
                            + "\n\nSunucudaki .env dosyasına TELEGRAM_ALLOWED_CHAT_ID="
                            + chat_id
                            + " yazıp servisi yeniden başlat.",
                        )
                        continue
                    reply = lambda response, recipient=chat_id: send_telegram(client, recipient, response)
                    await handle_message(f"telegram:{chat_id}", text, reply)
            except (httpx.HTTPError, RuntimeError) as error:
                print(f"Telegram polling error: {error}; retrying in 5s")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
