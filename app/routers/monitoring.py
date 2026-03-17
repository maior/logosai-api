"""Service monitoring endpoints."""

import time
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import aiohttp

from app.config import settings

router = APIRouter()

# Track server start time
_start_time = time.time()


@router.get("/monitoring/services")
async def service_status():
    """Check status of all LogosAI services."""

    async def check_service(name: str, url: str, timeout: float = 3.0):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return {
                        "name": name,
                        "url": url,
                        "status": "running" if resp.status < 500 else "error",
                        "http_code": resp.status,
                        "response_time_ms": round((time.time() - start) * 1000),
                    }
        except Exception as e:
            return {
                "name": name,
                "url": url,
                "status": "stopped",
                "http_code": 0,
                "error": str(e),
            }

    start = time.time()
    services = await asyncio.gather(
        check_service("logos_api", f"http://localhost:{settings.port}/health"),
        check_service("ACP Server", f"{settings.acp_server_url}/jsonrpc"),
    )

    # Self status
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_seconds,
        "services": list(services),
    }


@router.get("/monitoring/logs")
async def get_recent_logs(lines: int = 50, service: str = "all"):
    """Get recent log lines."""
    import os

    log_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(os.path.dirname(log_dir), "logs")

    result = {}
    log_files = {
        "acp": "acp.log",
        "api": "api.log",
        "web": "web.log",
    }

    if service != "all":
        log_files = {k: v for k, v in log_files.items() if k == service}

    for svc, filename in log_files.items():
        filepath = os.path.join(log_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    result[svc] = [line.rstrip() for line in all_lines[-lines:]]
            except Exception as e:
                result[svc] = [f"Error reading log: {e}"]
        else:
            result[svc] = []

    return {"logs": result}


@router.get("/monitoring/logs/stream")
async def stream_logs():
    """Stream logs in real-time via SSE."""
    import os

    log_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(os.path.dirname(log_dir), "logs")

    async def event_generator():
        import json

        files = {}
        log_names = {"acp.log": "acp", "api.log": "api", "web.log": "web"}

        # Open files and seek to end
        for filename, svc in log_names.items():
            filepath = os.path.join(log_dir, filename)
            if os.path.exists(filepath):
                f = open(filepath, "r", encoding="utf-8", errors="ignore")
                f.seek(0, 2)  # Seek to end
                files[svc] = f

        try:
            while True:
                has_data = False
                for svc, f in files.items():
                    line = f.readline()
                    if line:
                        has_data = True
                        data = json.dumps({"service": svc, "line": line.rstrip()})
                        yield f"data: {data}\n\n"

                if not has_data:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(1)
        finally:
            for f in files.values():
                f.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
