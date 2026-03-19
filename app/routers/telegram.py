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

def _clean_for_telegram(text: str) -> str:
    """Strip HTML/CSS/JS but keep Telegram-compatible Markdown."""
    import re

    # Remove entire <style>...</style> blocks
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove entire <script>...</script> blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove CSS @import statements
    text = re.sub(r'@import\s+url\([^)]+\);?', '', text)
    # Remove inline CSS (style="...")
    text = re.sub(r'\s*style="[^"]*"', '', text)
    # Remove CSS class attributes
    text = re.sub(r'\s*class="[^"]*"', '', text)
    # Remove all HTML tags but keep inner text
    text = re.sub(r'<[^>]+>', '', text)
    # Remove CSS property-like lines
    text = re.sub(r'^\s*[\w-]+\s*:\s*[^;]+;\s*$', '', text, flags=re.MULTILINE)
    # Remove CSS selectors and braces
    text = re.sub(r'^\s*[.#][\w-]+\s*\{.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\}\s*$', '', text, flags=re.MULTILINE)
    # Remove markdown images (not supported in Telegram)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'\2', text)
    # Convert ### headers to bold (Telegram doesn't support #)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # Clean up multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace per line
    text = '\n'.join(line.strip() for line in text.split('\n'))
    text = re.sub(r'^\n+|\n+$', '', text)
    return text.strip()


async def send_telegram_message(
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
):
    """Send a clean text message to Telegram chat."""
    if not settings.telegram_bot_token:
        logger.warning("Telegram bot token not configured")
        return

    url = f"{TELEGRAM_API.format(token=settings.telegram_bot_token)}/sendMessage"

    # Clean text for Telegram (remove HTML/markdown artifacts)
    clean_text = _clean_for_telegram(text)

    # Telegram has 4096 char limit — split if needed
    chunks = [clean_text[i:i+4000] for i in range(0, len(clean_text), 4000)]

    async with httpx.AsyncClient(timeout=30) as client:
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            }
            if reply_to_message_id and i == 0:
                payload["reply_to_message_id"] = reply_to_message_id

            try:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    # Markdown parsing failed — retry without parse_mode
                    payload.pop("parse_mode", None)
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

async def _format_for_telegram(query: str, raw_answer: str) -> str:
    """Use LLM to reformat agent response for Telegram's chat format.

    Converts long markdown/HTML responses into concise, mobile-friendly text.
    NEVER fabricates data — only reformats what exists.
    """
    if not raw_answer or len(raw_answer) < 20:
        return raw_answer

    try:
        from logosai.utils.llm_client import LLMClient
        import os

        google_key = os.getenv("GOOGLE_API_KEY", "")
        if not google_key:
            return _clean_for_telegram(raw_answer)

        llm = LLMClient(provider="google", model="gemini-2.5-flash-lite", temperature=0.3, max_tokens=1000)
        await llm.initialize()

        messages = [
            {"role": "system", "content": """You are a Telegram message formatter. Convert AI responses into clean, beautiful Telegram messages.

YOUR JOB:
1. Extract the KEY INFORMATION from the AI response
2. Format using Telegram Markdown:
   - *bold* for emphasis and headers
   - _italic_ for notes
   - `code` for values, numbers, filenames
   - [link text](url) for links
3. Use emoji for visual structure (📊 💰 📅 ✅ ⚠️ 💡 🔍 📁 📄 etc.)
4. Each key point on its own line
5. Same language as the original
6. Remove ALL HTML tags, CSS, JavaScript — only Telegram Markdown

ABSOLUTE PROHIBITION:
- NEVER INVENT or ADD information not in the original
- NEVER create fake data
- If the original has no useful content, say "정보를 찾을 수 없습니다"

Keep it concise and beautiful for mobile chat."""},
            {"role": "user", "content": f"User question: {query}\n\nAI response (extract key info, NEVER add new info):\n{_clean_for_telegram(raw_answer)[:3000]}"},
        ]

        result = await asyncio.wait_for(llm.invoke_messages(messages), timeout=10)
        formatted = result.strip() if isinstance(result, str) else str(result).strip()

        print(f"[TG_FORMAT] Input: {len(raw_answer)} chars → Output: {len(formatted)} chars")
        print(f"[TG_FORMAT] Preview: {formatted[:200]}")

        if formatted and len(formatted) > 20:
            if len(formatted) > len(raw_answer) * 2:
                print("[TG_FORMAT] BLOCKED — output too long, using original")
                return _clean_for_telegram(raw_answer)
            return _clean_for_telegram(formatted)

    except Exception as e:
        print(f"[TG_FORMAT] LLM failed: {e}")

    # Fallback to basic cleanup
    return _clean_for_telegram(raw_answer)


async def process_telegram_message(chat_id: int, user_id: str, text: str, message_id: int):
    """Process a Telegram message through LogosAI pipeline."""
    from app.database import get_db_context
    from app.services.chat_service import ChatService
    from app.services.user_service import UserService
    from app.schemas.chat import ChatRequest

    # Start periodic typing indicator (every 4 seconds)
    typing_flag = [True]  # Use list for mutable closure

    async def keep_typing():
        while typing_flag[0]:
            try:
                await send_typing_action(chat_id)
            except Exception:
                pass
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(keep_typing())

    try:
        async with get_db_context() as db:
            chat_service = ChatService(db)

            # Get or create user from telegram ID
            telegram_email = f"telegram_{user_id}@logosai.info"
            user_service = UserService(db)
            user = await user_service.get_by_email(telegram_email)
            if not user:
                from app.schemas.user import UserCreate
                user = await user_service.create(UserCreate(
                    email=telegram_email,
                    name=f"Telegram User {user_id}",
                ))
                await db.commit()

            request = ChatRequest(
                query=text,
                session_id=None,  # Auto-create/find session
                project_id=None,
            )

            # Stream and collect final result
            final_answer = ""
            async for event in chat_service.stream_chat(
                user_id=user.id,
                request=request,
                user_email=telegram_email,
            ):
                event_type = event.get("event", "")

                # Capture final result
                if event_type == "final_result":
                    data = event.get("data", {})
                    inner = data.get("data", data)
                    final_answer = inner.get("result", "")

            # Stop typing
            typing_flag[0] = False
            typing_task.cancel()

            if final_answer:
                # Check if the answer is actually an error message
                error_indicators = ["오류가 발생했습니다", "Error:", "Traceback", "Exception", "에이전트가 현재 사용 불가"]
                is_error = any(ind in final_answer for ind in error_indicators)

                if is_error:
                    await send_telegram_message(
                        chat_id,
                        "⚠️ 요청을 처리하는 중 문제가 발생했습니다. 다시 시도해주세요.",
                        reply_to_message_id=message_id,
                    )
                else:
                    # Reformat for Telegram's chat format
                    formatted = await _format_for_telegram(text, final_answer)
                    await send_telegram_message(chat_id, formatted, reply_to_message_id=message_id)
            else:
                await send_telegram_message(
                    chat_id,
                    "죄송합니다. 응답을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
                    reply_to_message_id=message_id,
                )

    except Exception as e:
        typing_flag[0] = False
        typing_task.cancel()
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
            f"저는 LogosAI 챗봇입니다.\n"
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
            "LogosAI 사용법 🤖\n\n"
            "자유롭게 질문하면 최적의 에이전트가 자동 선택됩니다.\n\n"
            "사용 가능한 기능:\n"
            "- 💬 일반 대화 / Q&A\n"
            "- 🔍 인터넷 검색\n"
            "- 🌐 번역 (10개 언어)\n"
            "- 💻 코드 생성/설명\n"
            "- 📝 요약\n"
            "- ✍️ 문서 작성\n"
            "- 🧮 계산\n\n"
            "명령어:\n"
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
