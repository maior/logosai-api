"""Memory service for user memory CRUD and LLM-based extraction.

Provides:
- CRUD operations for user memories
- Context loading for LLM prompt injection
- LLM-based memory extraction from conversations
"""

import json
import logging
import math
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logosus.memory import UserMemory

logger = logging.getLogger(__name__)

# Memory extraction prompt for Gemini
EXTRACTION_PROMPT = """사용자와 AI의 대화를 분석하여, **사용자에 대해 장기적으로 기억할 가치가 있는 정보만** 추출하세요.

## 기존 메모리 (중복 금지)
{existing_memories}

## 대화 내용
{messages}

## 추출 대상 (이것만 추출)
- fact: 사용자 본인에 대한 객관적 사실 (직업, 거주지, 소속, 이름, 전공, 나이)
- preference: 사용자가 명시적으로 표현한 선호/취향 (응답 스타일, 선호 언어, 도구 선호)
- instruction: 사용자가 AI에게 명시적으로 요청한 지속적 지시 ("항상 ~해줘", "앞으로 ~하지 마")
- context: 사용자가 직접 언급한 장기적 상황 (진행 중 프로젝트명, 학기, 회사명)

## 추출하면 안 되는 것 (중요!)
- 단순 검색/조회 쿼리 (날씨, 환율, 뉴스, 시세 등) → 기억 가치 없음
- AI가 생성한 응답 내용 (검색 결과, 계산 결과, 번역 결과 등) → 사용자 정보 아님
- 일회성 작업 요청 ("이메일 써줘", "번역해줘", "요약해줘") → 지시가 아닌 단순 요청
- 스케줄/일정 데이터 (AI가 DB에서 조회한 일정 목록) → 이미 DB에 저장됨
- 메모 조회/생성 요청 → 이미 메모 시스템에 저장됨
- 대화의 주제나 토픽 자체 ("양자컴퓨터에 대해 물어봄") → 검색 기록이지 사용자 정보 아님

## 판단 기준
- "이 정보가 다음 대화에서 사용자를 더 잘 도울 수 있는가?" → Yes면 추출
- "단순히 사용자가 이런 질문을 했다는 사실인가?" → Yes면 추출 금지
- 확신이 없으면 추출하지 않음 (빈 배열 반환)

## 중요도 기준
- 0.9-1.0: 모든 응답에 영향 (예: 선호 언어, 지속적 지시)
- 0.7-0.8: 관련 쿼리에 영향 (예: 직업, 전공)
- 0.4-0.6: 참고 수준 (예: 관심 분야)

## 금지사항
- 기존 메모리와 중복되는 정보 추출 금지
- 비밀번호, 주민번호 등 민감 정보 추출 금지
- 대부분의 대화에서는 추출할 것이 없음 → 빈 배열 반환이 정상

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)
{{"memories": [{{"memory_type":"...", "content":"...", "category":"...", "importance":0.0}}]}}"""


_TYPE_CONFIG = {
    "instruction": {"header": "지시사항", "guide": "항상 적용"},
    "preference": {"header": "선호도", "guide": "사용자가 명시적으로 다른 것을 요청하지 않는 한 적용"},
    "fact": {"header": "사용자 정보", "guide": "쿼리와 관련 있을 때만 활용"},
    "context": {"header": "현재 맥락", "guide": "관련 있을 때만 참고"},
}
_TYPE_ORDER = ["instruction", "preference", "fact", "context"]


class MemoryService:
    """Service for user memory operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================
    # CRUD Operations
    # ============================

    async def get_memories_for_user(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[UserMemory]:
        """Get memories for a user with optional filtering."""
        conditions = [UserMemory.user_id == user_id]

        if active_only:
            conditions.append(UserMemory.is_active == True)
        if memory_type:
            conditions.append(UserMemory.memory_type == memory_type)

        stmt = (
            select(UserMemory)
            .where(and_(*conditions))
            .order_by(UserMemory.importance.desc(), UserMemory.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_memory_by_id(self, memory_id: str) -> Optional[UserMemory]:
        """Get a single memory by ID."""
        result = await self.db.execute(
            select(UserMemory).where(UserMemory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def create_memory(
        self,
        user_id: str,
        data: dict,
        conversation_id: Optional[str] = None,
    ) -> UserMemory:
        """Create a new user memory."""
        memory = UserMemory(
            id=str(uuid4()),
            user_id=user_id,
            memory_type=data["memory_type"],
            content=data["content"],
            category=data.get("category"),
            importance=data.get("importance", 0.5),
            source_conversation_id=conversation_id,
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    async def update_memory(self, memory: UserMemory, data: dict) -> UserMemory:
        """Update an existing memory."""
        for key, value in data.items():
            if value is not None and hasattr(memory, key):
                setattr(memory, key, value)
        await self.db.flush()
        return memory

    async def delete_memory(self, memory: UserMemory) -> None:
        """Soft-delete a memory by deactivating it."""
        memory.is_active = False
        await self.db.flush()

    # ============================
    # Context Loading (for LLM)
    # ============================

    async def load_memories_for_context(
        self,
        user_id: str,
        max_memories: int = 20,
    ) -> Optional[str]:
        """Load and format user memories for LLM context injection.

        Scores memories by importance * recency_weight (30-day half-life)
        and returns top N as formatted text.

        Returns None if no memories found.
        """
        # Get all active memories
        stmt = (
            select(UserMemory)
            .where(
                and_(
                    UserMemory.user_id == user_id,
                    UserMemory.is_active == True,
                )
            )
        )
        result = await self.db.execute(stmt)
        memories = list(result.scalars().all())

        if not memories:
            return None

        # Score by importance * recency
        now = datetime.now(timezone.utc)
        scored = []
        for m in memories:
            days_old = (now - m.created_at).total_seconds() / 86400
            recency_weight = math.pow(0.5, days_old / 30)  # 30-day half-life
            score = m.importance * recency_weight
            scored.append((m, score))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[1], reverse=True)
        top_memories = scored[:max_memories]

        # Update access tracking
        memory_ids = [m.id for m, _ in top_memories]
        if memory_ids:
            await self.db.execute(
                update(UserMemory)
                .where(UserMemory.id.in_(memory_ids))
                .values(
                    access_count=UserMemory.access_count + 1,
                    last_accessed_at=now,
                )
            )

        # Format as grouped context string
        grouped: dict[str, list[str]] = {}
        for m, score in top_memories:
            cat = f"({m.category}) " if m.category else ""
            grouped.setdefault(m.memory_type, []).append(f"- {cat}{m.content}")

        lines = ["## 사용자 메모리"]
        for mtype in _TYPE_ORDER:
            items = grouped.get(mtype)
            if not items:
                continue
            cfg = _TYPE_CONFIG.get(mtype, {"header": mtype, "guide": "참고"})
            lines.append(f"\n### {cfg['header']} ({cfg['guide']})")
            lines.extend(items)

        return "\n".join(lines)

    # ============================
    # LLM-based Memory Extraction
    # ============================

    async def extract_memories_from_conversation(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[dict],
    ) -> list[UserMemory]:
        """Extract memories from a conversation using LLM.

        Args:
            user_id: User UUID
            conversation_id: Source conversation UUID
            messages: List of {"role": "user"/"assistant", "content": "..."}

        Returns:
            List of newly created UserMemory objects
        """
        # Load existing memories to avoid duplicates
        existing = await self.get_memories_for_user(user_id, active_only=True, limit=100)
        existing_text = "\n".join(
            f"- [{m.memory_type}] {m.content}" for m in existing
        ) or "(없음)"

        # Format messages
        messages_text = "\n".join(
            f"{'사용자' if m['role'] == 'user' else 'AI'}: {m['content']}"
            for m in messages
        )

        # Build prompt
        prompt = EXTRACTION_PROMPT.format(
            existing_memories=existing_text,
            messages=messages_text,
        )

        # Call Gemini LLM
        try:
            extracted = await self._call_gemini(prompt)
        except Exception as e:
            logger.warning(f"Memory extraction LLM call failed: {e}")
            return []

        # Parse and create memories
        new_memories = []
        for item in extracted:
            memory_type = item.get("memory_type", "context")
            content = item.get("content", "").strip()

            if not content:
                continue

            # Skip if too similar to existing
            if any(content.lower() in m.content.lower() or m.content.lower() in content.lower() for m in existing):
                logger.debug(f"Skipping duplicate memory: {content[:50]}")
                continue

            memory = await self.create_memory(
                user_id=user_id,
                data={
                    "memory_type": memory_type if memory_type in ("fact", "preference", "context", "instruction") else "context",
                    "content": content,
                    "category": item.get("category"),
                    "importance": min(max(item.get("importance", 0.5), 0.0), 1.0),
                },
                conversation_id=conversation_id,
            )
            new_memories.append(memory)
            logger.info(f"Extracted memory [{memory_type}]: {content[:60]}")

        if new_memories:
            await self.db.commit()
            logger.info(f"Extracted {len(new_memories)} memories for user {user_id[:8]}...")

        return new_memories

    async def _call_gemini(self, prompt: str) -> list[dict]:
        """Call Gemini LLM for memory extraction and return parsed list."""
        try:
            from google import genai
        except ImportError:
            logger.error("google-genai not installed. Run: pip install google-genai")
            return []

        import os
        from app.config import settings

        api_key = settings.google_api_key or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            logger.warning("google_api_key not set in config. Memory extraction disabled.")
            return []

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )

            # Parse JSON response
            text = response.text.strip()

            # Remove markdown code block markers if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            data = json.loads(text)
            memories = data.get("memories", [])

            if not isinstance(memories, list):
                logger.warning(f"Unexpected LLM response format: {text[:100]}")
                return []

            return memories

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")
            return []
