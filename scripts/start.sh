#!/bin/bash

# logos_api 시작 스크립트
# Usage: ./scripts/start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOGOS_ROOT="$(dirname "$PROJECT_DIR")"
PID_FILE="$PROJECT_DIR/logs/logos_api.pid"
LOG_FILE="$PROJECT_DIR/logs/logos_api.log"
PORT=8090

cd "$PROJECT_DIR"

# 로그 디렉토리 생성
mkdir -p "$PROJECT_DIR/logs"

# 가상환경 확인 및 활성화
if [ -f "$LOGOS_ROOT/.venv/bin/activate" ]; then
    source "$LOGOS_ROOT/.venv/bin/activate"
elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
else
    echo "❌ 가상환경을 찾을 수 없습니다"
    echo "   $LOGOS_ROOT/.venv 또는 $PROJECT_DIR/.venv 확인"
    exit 1
fi

# 이미 실행 중인지 확인
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "logos_api가 이미 실행 중입니다 (PID: $OLD_PID)"
        echo "중지하려면: ./scripts/stop.sh"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# 포트가 사용 중인지 확인
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "⚠️  포트 $PORT이 이미 사용 중입니다"
    lsof -i :$PORT
    echo ""
    echo "기존 프로세스를 종료하고 시작하려면: ./scripts/restart.sh"
    exit 1
fi

echo "🚀 logos_api 시작 중..."
echo "   포트: $PORT"
echo "   로그: $LOG_FILE"

# Uvicorn 서버 시작
nohup uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload >> "$LOG_FILE" 2>&1 &
NEW_PID=$!

# PID 저장
echo $NEW_PID > "$PID_FILE"

# 서버 시작 대기
sleep 3

# 시작 확인
if ps -p $NEW_PID > /dev/null 2>&1; then
    # Health check
    sleep 2
    if curl -s --max-time 5 http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "✅ logos_api 시작 완료 (PID: $NEW_PID)"
        echo "   URL: http://localhost:$PORT"
        echo "   Docs: http://localhost:$PORT/docs"
    else
        echo "⚠️  logos_api 시작됨, health check 대기 중..."
        echo "   PID: $NEW_PID"
    fi
else
    echo "❌ logos_api 시작 실패"
    cat "$LOG_FILE" | tail -20
    rm -f "$PID_FILE"
    exit 1
fi
