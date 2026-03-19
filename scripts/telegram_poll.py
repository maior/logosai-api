#!/usr/bin/env python3
"""
Telegram Bot Polling Mode — for local development.

Polls Telegram for new messages and forwards them to logos_api webhook.
Use this when your server isn't publicly accessible (localhost).

Usage:
    python scripts/telegram_poll.py

Requires:
    TELEGRAM_BOT_TOKEN in .env
"""

import asyncio
import os
import sys
import httpx

# Load .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_URL = os.getenv("LOGOS_API_URL", "http://localhost:8090")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


async def get_updates(offset: int = 0) -> list:
    """Get new messages from Telegram."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 20},
        )
        data = resp.json()
        return data.get("result", [])


async def forward_to_api(update: dict):
    """Forward Telegram update to logos_api webhook."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{API_URL}/api/v1/telegram/webhook",
            json=update,
        )
        return resp.json()


async def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    # Delete webhook first (polling and webhook can't coexist)
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/deleteWebhook")

    # Get bot info
    async with httpx.AsyncClient() as client:
        me = await client.get(f"{TELEGRAM_API}/getMe")
        bot = me.json().get("result", {})
        print(f"🤖 Bot: @{bot.get('username', '?')} ({bot.get('first_name', '?')})")
        print(f"📡 Polling mode — forwarding to {API_URL}")
        print(f"💬 Send a message to @{bot.get('username', '?')} on Telegram")
        print()

    offset = 0
    while True:
        try:
            updates = await get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                user = msg.get("from", {}).get("first_name", "?")

                if text:
                    print(f"📩 {user}: {text}")
                    result = await forward_to_api(update)
                    print(f"   → {result}")

        except KeyboardInterrupt:
            print("\n👋 Stopped")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
