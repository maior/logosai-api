#!/bin/bash

# logos_api 중지 스크립트
# Usage: ./scripts/stop.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/logs/logos_api.pid"
PORT=8090

echo "🛑 logos_api 중지 중..."

# PID 파일로 종료
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID" 2>/dev/null
        sleep 2
        # 강제 종료 필요시
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null
        fi
        echo "✅ PID $PID 프로세스 종료됨"
    fi
    rm -f "$PID_FILE"
fi

# 포트로 실행 중인 프로세스 종료
PIDS=$(lsof -t -i :$PORT 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "포트 $PORT 프로세스 종료 중: $PIDS"
    echo "$PIDS" | xargs kill 2>/dev/null
    sleep 1
    # 강제 종료
    PIDS=$(lsof -t -i :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi
fi

# Uvicorn 관련 프로세스 정리
pkill -f "uvicorn.*$PORT" 2>/dev/null

echo "✅ logos_api 중지 완료"
