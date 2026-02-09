#!/bin/bash

# logos_api 상태 확인 스크립트
# Usage: ./scripts/status.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/logs/logos_api.pid"
PORT=8090

echo "📊 logos_api 상태 확인"
echo "========================"

# PID 파일 확인
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ 상태: 실행 중"
        echo "   PID: $PID"
    else
        echo "⚠️  상태: PID 파일 있으나 프로세스 없음"
        rm -f "$PID_FILE"
    fi
else
    echo "❌ 상태: PID 파일 없음"
fi

# 포트 확인
echo ""
echo "🔌 포트 $PORT 상태:"
if lsof -i :$PORT > /dev/null 2>&1; then
    lsof -i :$PORT | head -5
else
    echo "   사용 중인 프로세스 없음"
fi

# Health check
echo ""
echo "🏥 Health Check:"
HEALTH_RESPONSE=$(curl -s --max-time 5 http://localhost:$PORT/health 2>/dev/null)
if [ -n "$HEALTH_RESPONSE" ]; then
    echo "   ✅ http://localhost:$PORT/health 응답 정상"
    echo "   $HEALTH_RESPONSE"
else
    echo "   ❌ http://localhost:$PORT/health 응답 없음"
fi

# ACP 서버 연결 확인
echo ""
echo "📡 ACP Server 연결 상태:"
CHAT_HEALTH=$(curl -s --max-time 5 http://localhost:$PORT/api/v1/chat/health 2>/dev/null)
if [ -n "$CHAT_HEALTH" ]; then
    echo "   $CHAT_HEALTH"
else
    echo "   ❌ ACP 연결 상태 확인 불가"
fi

# 최근 로그
echo ""
echo "📝 최근 로그 (마지막 10줄):"
if [ -f "$PROJECT_DIR/logs/logos_api.log" ]; then
    tail -10 "$PROJECT_DIR/logs/logos_api.log" | grep -v "^$"
else
    echo "   로그 파일 없음"
fi
