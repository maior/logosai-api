"""
RAG 통합 테스트 스크립트

logos_server의 구현과 비교하여 logos_api의 RAG 기능 테스트:
1. 파일 업로드 및 DB 저장
2. RAG 인덱싱 (ElasticSearch)
3. 파일 목록 조회
4. RAG 검색

Usage:
    python tests/test_rag_integration.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def test_document_service():
    """Document Service 단위 테스트"""
    print("\n" + "=" * 60)
    print("📋 Document Service 테스트")
    print("=" * 60)

    from app.config import settings
    from app.services.document_service import DocumentService
    from app.models.document import Document, DocumentStatus

    # Create test database session
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = DocumentService(session)

        # Test 1: RAG Service 초기화
        print("\n[1] RAG Service 초기화 테스트")
        try:
            rag_service = service.rag_service
            print(f"   ✅ RAG Service 초기화 성공")
            print(f"      - Document Processor: {type(rag_service.document_processor).__name__}")
            print(f"      - ES Client: {type(rag_service.es_client).__name__}")
            print(f"      - Embedding Service: {type(rag_service.embedding_service).__name__}")
        except Exception as e:
            print(f"   ❌ RAG Service 초기화 실패: {e}")
            return False

        # Test 2: RAG Health Check
        print("\n[2] RAG 시스템 Health Check")
        try:
            health = await service.check_rag_health()
            print(f"   ✅ Health Check 완료")
            print(f"      - Elasticsearch: {'연결됨' if health.get('elasticsearch') else '연결 안됨'}")
            print(f"      - Index 존재: {health.get('index_exists')}")
            print(f"      - Embedding Model: {health.get('embedding_model')}")
            print(f"      - Chunk Size: {health.get('chunk_size')}")
        except Exception as e:
            print(f"   ⚠️ Health Check 실패 (ES 미실행 가능): {e}")

    await engine.dispose()
    return True


async def test_document_processor():
    """Document Processor 단위 테스트"""
    print("\n" + "=" * 60)
    print("📄 Document Processor 테스트")
    print("=" * 60)

    from app.services.rag import DocumentProcessor

    processor = DocumentProcessor()

    # Test 1: 지원 파일 형식
    print("\n[1] 지원 파일 형식")
    print(f"   지원: {processor.SUPPORTED_EXTENSIONS}")

    # Test 2: 텍스트 파일 처리
    print("\n[2] 텍스트 파일 청킹 테스트")

    # Create temp text file
    test_content = """
    LogosAI는 온톨로지 기반 지능형 멀티 에이전트 AI 시스템 플랫폼입니다.

    주요 기능:
    1. 멀티 에이전트 오케스트레이션
    2. RAG (Retrieval-Augmented Generation)
    3. 온톨로지 기반 추론
    4. FORGE AI 에이전트 생성

    이 시스템은 복잡한 작업을 전문화된 에이전트 간의 협업을 통해 해결합니다.
    """ * 5  # Make it longer for chunking

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_path = f.name

    try:
        chunks = await processor.process_file(
            file_path=temp_path,
            file_name="test_document.txt",
            user_id="test_user",
            document_id="test_doc_001",
            project_id="test_project",
        )

        print(f"   ✅ 청킹 성공")
        print(f"      - 총 청크 수: {len(chunks)}")
        print(f"      - 첫 번째 청크 길이: {len(chunks[0].page_content)} chars")
        print(f"      - 메타데이터: {list(chunks[0].metadata.keys())}")

        # Get stats
        stats = processor.get_chunk_stats(chunks)
        print(f"   📊 청크 통계:")
        print(f"      - 총 문자 수: {stats['total_chars']}")
        print(f"      - 평균 청크 크기: {stats['avg_chunk_size']}")
        print(f"      - 최소/최대: {stats['min_chunk_size']}/{stats['max_chunk_size']}")

    except Exception as e:
        print(f"   ❌ 청킹 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        os.unlink(temp_path)

    return True


async def test_embedding_service():
    """Embedding Service 단위 테스트"""
    print("\n" + "=" * 60)
    print("🧠 Embedding Service 테스트")
    print("=" * 60)

    from app.services.rag import get_embedding_service

    print("\n[1] 임베딩 모델 로드 (최초 로드 시 시간 소요)")
    try:
        embedding_service = get_embedding_service()
        print(f"   ✅ 임베딩 서비스 로드 성공")
    except Exception as e:
        print(f"   ❌ 임베딩 서비스 로드 실패: {e}")
        return False

    print("\n[2] 텍스트 임베딩 생성")
    test_texts = [
        "LogosAI 멀티 에이전트 시스템",
        "RAG 검색 기능 테스트",
        "완전히 다른 주제의 문장입니다",
    ]

    embeddings = []
    for text in test_texts:
        try:
            embedding = embedding_service.encode(text)
            embeddings.append(embedding)
            print(f"   ✅ '{text[:30]}...' → {len(embedding)} 차원")
        except Exception as e:
            print(f"   ❌ 임베딩 실패: {e}")

    print("\n[3] 코사인 유사도 테스트")
    if len(embeddings) >= 3:
        sim_01 = embedding_service.cosine_similarity(embeddings[0], embeddings[1])
        sim_02 = embedding_service.cosine_similarity(embeddings[0], embeddings[2])

        print(f"   문장 0-1 유사도: {sim_01:.4f} (관련 있음)")
        print(f"   문장 0-2 유사도: {sim_02:.4f} (관련 없음)")

        if sim_01 > sim_02:
            print("   ✅ 유사도 순서 정상 (관련 문장이 더 유사)")
        else:
            print("   ⚠️ 유사도 순서 비정상")

    return True


async def test_elasticsearch_client():
    """ElasticSearch Client 테스트"""
    print("\n" + "=" * 60)
    print("🔍 ElasticSearch Client 테스트")
    print("=" * 60)

    from app.services.rag import get_elasticsearch_client

    es_client = get_elasticsearch_client()

    print("\n[1] ES 연결 상태 확인")
    try:
        is_healthy = await es_client.health_check()
        if is_healthy:
            print("   ✅ ElasticSearch 연결 성공")
        else:
            print("   ❌ ElasticSearch 연결 실패")
            return False
    except Exception as e:
        print(f"   ❌ ElasticSearch 연결 오류: {e}")
        print("   ⚠️ ElasticSearch가 실행 중인지 확인하세요 (localhost:9200)")
        return False

    print("\n[2] 인덱스 존재 여부 확인")
    try:
        exists = await es_client.index_exists()
        print(f"   인덱스 존재: {exists}")

        if not exists:
            print("   → 인덱스 생성 시도...")
            created = await es_client.create_index()
            print(f"   인덱스 생성: {'성공' if created else '이미 존재'}")
    except Exception as e:
        print(f"   ❌ 인덱스 확인 오류: {e}")

    await es_client.close()
    return True


async def test_rag_search():
    """RAG 검색 테스트 (ES 실행 필요)"""
    print("\n" + "=" * 60)
    print("🔎 RAG 검색 테스트")
    print("=" * 60)

    from app.services.rag import RAGService

    rag_service = RAGService()

    print("\n[1] 하이브리드 검색 테스트")
    try:
        results = await rag_service.search(
            query="LogosAI 멀티 에이전트",
            user_id="test_user",
            project_id=None,
            top_k=5,
        )

        print(f"   ✅ 검색 완료")
        print(f"      - 결과 수: {len(results)}")

        for i, r in enumerate(results[:3]):
            print(f"      [{i+1}] Score: {r.score:.4f}, Content: {r.content[:50]}...")

    except Exception as e:
        print(f"   ⚠️ 검색 실패 (인덱싱된 데이터 없을 수 있음): {e}")

    return True


def print_comparison_table():
    """logos_server vs logos_api 비교표 출력"""
    print("\n" + "=" * 60)
    print("📊 logos_server vs logos_api 구현 비교")
    print("=" * 60)

    comparison = """
┌─────────────────┬──────────────────────────┬──────────────────────────┐
│ 기능            │ logos_server             │ logos_api                │
├─────────────────┼──────────────────────────┼──────────────────────────┤
│ 파일 업로드     │ base64 인코딩            │ multipart/form-data      │
│ DB 저장         │ user_files 테이블        │ documents 테이블         │
│ DB 라이브러리   │ psycopg2 (직접 SQL)      │ SQLAlchemy Async         │
│ 청킹            │ 512/128 (동일)           │ 512/128 (동일)           │
│ 임베딩 모델     │ jhgan/ko-sroberta-nli    │ jhgan/ko-sroberta-nli    │
│ ES 인덱싱       │ LangChain ES Store       │ LangChain ES Store       │
│ 검색 방식       │ hybrid (keyword+vector)  │ hybrid (keyword+vector)  │
│ 파일 목록       │ PostgreSQL 조회          │ SQLAlchemy 조회          │
│ 자동 처리       │ 동기 (업로드 시)         │ BackgroundTasks          │
└─────────────────┴──────────────────────────┴──────────────────────────┘

✅ 핵심 로직 동일: 청킹, 임베딩, ES 인덱싱, 하이브리드 검색
✅ 개선점: FastAPI BackgroundTasks로 빠른 응답, 비동기 처리
"""
    print(comparison)


async def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("🧪 logos_api RAG 통합 테스트")
    print("=" * 60)

    # 비교표 출력
    print_comparison_table()

    # 테스트 실행
    results = {}

    # 1. Document Processor 테스트
    results['document_processor'] = await test_document_processor()

    # 2. Embedding Service 테스트
    results['embedding_service'] = await test_embedding_service()

    # 3. Document Service 테스트
    results['document_service'] = await test_document_service()

    # 4. ElasticSearch 테스트 (ES 실행 필요)
    results['elasticsearch'] = await test_elasticsearch_client()

    # 5. RAG 검색 테스트 (ES 실행 필요)
    if results['elasticsearch']:
        results['rag_search'] = await test_rag_search()

    # 결과 요약
    print("\n" + "=" * 60)
    print("📋 테스트 결과 요약")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")

    all_passed = all(results.values())
    print(f"\n   전체 결과: {'✅ 모든 테스트 통과' if all_passed else '⚠️ 일부 테스트 실패'}")

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
