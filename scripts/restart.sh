#!/bin/bash

# logos_api 재시작 스크립트
# Usage: ./scripts/restart.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔄 logos_api 재시작 중..."

# 중지
"$SCRIPT_DIR/stop.sh"

# 잠시 대기
sleep 2

# 시작
"$SCRIPT_DIR/start.sh"
