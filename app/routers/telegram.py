"""Telegram Bot webhook integration.

Receives messages from Telegram, processes them through LogosAI,
and sends responses back. Uses the same pipeline as the web chat.

Setup:
  1. Create bot via @BotFather on Telegram
  2. Set TELEGRAM_BOT_TOKEN in .env
  3. Register webhook: POST /api/v1/telegram/register-webhook

Architecture:
  Telegram → webhook → logos_api → orchestrator → ACP agents
                                       ↓
  Telegram ← send_message ← logos_api ← response
"""

import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
import httpx

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

TELEGRAM_API = "https://api.telegram.org/bot{token}"


# ═══════════════════════════════════════
# Telegram API helpers
# ═══════════════════════════════════════

async def send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
    reply_to_message_id: Optional[int] = None,
):
    """Send a message to Telegram chat."""
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured")
        return

    url = f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/sendMessage"

    # Telegram has 4096 char limit — split if needed
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

    async with httpx.AsyncClient(timeout=30) as client:
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
            }
            if reply_to_message_id and i == 0:
                payload["reply_to_message_id"] = reply_to_message_id

            try:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    # Retry without parse_mode (markdown may be invalid)
                    payload["parse_mode"] = None
                    await client.post(url, json=payload)
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")


async def send_typing_action(chat_id: int):
    """Show 'typing...' indicator in Telegram."""
    if not settings.telegram_bot_token:
        return

    url = f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/sendChatAction"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"chat_id": chat_id, "action": "typing"})


# ═══════════════════════════════════════
# Chat processing
# ═══════════════════════════════════════

async def process_telegram_message(chat_id: int, user_id: str, text: str, message_id: int):
    """Process a Telegram message through LogosAI pipeline."""
    from app.database import get_db_context
    from app.services.chat_service import ChatService
    from app.services.orchestrator_service import get_orchestrator_service
    from app.schemas.chat import ChatRequest

    # Show typing indicator
    await send_typing_action(chat_id)

    try:
        async with get_db_context() as db:
            orchestrator = await get_orchestrator_service()
            chat_service = ChatService(db, orchestrator_service=orchestrator)

            # Use telegram user_id as email (for user identification)
            telegram_email = f"telegram_{user_id}@logosai.local"

            request = ChatRequest(
                query=text,
                session_id=None,  # Auto-create/find session
                project_id=None,
            )

            # Stream and collect final result
            final_answer = ""
            async for event in chat_service.stream_chat(
                user_id=telegram_email,
                request=request,
                user_email=telegram_email,
            ):
                event_type = event.get("event", "")

                # Send typing indicator periodically
                if event_type in ("agent_started", "planning_complete"):
                    await send_typing_action(chat_id)

                # Capture final result
                if event_type == "final_result":
                    data = event.get("data", {})
                    inner = data.get("data", data)
                    final_answer = inner.get("result", "")

            if final_answer:
                await send_telegram_message(chat_id, final_answer, reply_to_message_id=message_id)
            else:
                await send_telegram_message(
                    chat_id,
                    "죄송합니다. 응답을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
                    reply_to_message_id=message_id,
                )

    except Exception as e:
        logger.error(f"Telegram processing error: {e}")
        await send_telegram_message(
            chat_id,
            f"오류가 발생했습니다: {str(e)[:200]}",
            reply_to_message_id=message_id,
        )


# ═══════════════════════════════════════
# Webhook endpoints
# ═══════════════════════════════════════

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates.

    Telegram sends JSON with message updates to this endpoint.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")

    body = await request.json()

    # Extract message
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}  # Ignore non-message updates

    chat_id = message["chat"]["id"]
    user_id = str(message["from"]["id"])
    text = message.get("text", "")

    if not text:
        return {"ok": True}  # Ignore non-text messages

    # Handle /start command
    if text == "/start":
        user_name = message["from"].get("first_name", "")
        await send_telegram_message(
            chat_id,
            f"안녕하세요 {user_name}님! 👋\n\n"
            f"저는 **LogosAI** 챗봇입니다.\n"
            f"무엇이든 물어보세요. 인터넷 검색, 번역, 코드 생성, 요약 등 다양한 에이전트가 도와드립니다.\n\n"
            f"예시:\n"
            f"- 테슬라 주식 어때?\n"
            f"- 이 문장을 영어로 번역해줘\n"
            f"- Python으로 정렬 알고리즘 만들어줘\n"
            f"- 양자역학이란?",
        )
        return {"ok": True}

    # Handle /help command
    if text == "/help":
        await send_telegram_message(
            chat_id,
            "**LogosAI 사용법** 🤖\n\n"
            "자유롭게 질문하면 최적의 에이전트가 자동 선택됩니다.\n\n"
            "**사용 가능한 기능:**\n"
            "- 💬 일반 대화 / Q&A\n"
            "- 🔍 인터넷 검색\n"
            "- 🌐 번역 (10개 언어)\n"
            "- 💻 코드 생성/설명\n"
            "- 📝 요약\n"
            "- ✍️ 문서 작성\n"
            "- 🧮 계산\n\n"
            "**명령어:**\n"
            "/start - 시작\n"
            "/help - 도움말",
        )
        return {"ok": True}

    # Process message in background (don't block Telegram webhook timeout)
    asyncio.create_task(
        process_telegram_message(chat_id, user_id, text, message["message_id"])
    )

    return {"ok": True}


@router.post("/telegram/register-webhook")
async def register_webhook(request: Request):
    """Register this server as Telegram webhook.

    Call this once after deploying to set up the webhook URL.
    Requires the server to be publicly accessible (HTTPS).
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not set in .env")

    body = await request.json()
    webhook_url = body.get("webhook_url")

    if not webhook_url:
        # Auto-detect from request
        host = request.headers.get("host", "localhost:8090")
        scheme = request.headers.get("x-forwarded-proto", "http")
        webhook_url = f"{scheme}://{host}/api/v1/telegram/webhook"

    url = f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/setWebhook"

    payload = {
        "url": webhook_url,
        "allowed_updates": ["message", "edited_message"],
    }
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        result = resp.json()

    logger.info(f"Telegram webhook registered: {webhook_url} — {result}")

    return {
        "webhook_url": webhook_url,
        "telegram_response": result,
    }


@router.delete("/telegram/webhook")
async def remove_webhook():
    """Remove Telegram webhook."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not set")

    url = f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/deleteWebhook"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url)
        result = resp.json()

    return result


@router.get("/telegram/status")
async def telegram_status():
    """Check Telegram bot status and webhook info."""
    if not settings.telegram_bot_token:
        return {"configured": False, "message": "TELEGRAM_BOT_TOKEN not set"}

    async with httpx.AsyncClient(timeout=10) as client:
        # Get bot info
        me_resp = await client.get(
            f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/getMe"
        )
        me = me_resp.json()

        # Get webhook info
        wh_resp = await client.get(
            f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/getWebhookInfo"
        )
        webhook = wh_resp.json()

    return {
        "configured": True,
        "bot": me.get("result", {}),
        "webhook": webhook.get("result", {}),
    }
