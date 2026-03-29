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

    async def check_service(name: str, url: str, timeout: float = 3.0, method: str = "GET", json_body: dict | None = None):
        try:
            start_t = time.time()
            async with aiohttp.ClientSession() as session:
                if method == "POST" and json_body:
                    async with session.post(url, json=json_body, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                        return {
                            "name": name, "url": url,
                            "status": "running" if resp.status < 400 else "error",
                            "http_code": resp.status,
                            "response_time_ms": round((time.time() - start_t) * 1000),
                        }
                else:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                        return {
                            "name": name, "url": url,
                            "status": "running" if resp.status < 400 else "error",
                            "http_code": resp.status,
                            "response_time_ms": round((time.time() - start_t) * 1000),
                        }
        except Exception as e:
            return {
                "name": name, "url": url,
                "status": "stopped", "http_code": 0,
                "error": str(e),
            }

    start = time.time()
    services = await asyncio.gather(
        check_service("logos_api", f"http://localhost:{settings.port}/health"),
        check_service("ACP Server", f"{settings.acp_server_url}/jsonrpc", method="POST",
                       json_body={"jsonrpc": "2.0", "id": 1, "method": "get_server_info"}),
        check_service("logos_web", "http://localhost:8010/api/health"),
        check_service("FORGE", "http://localhost:8030/health"),
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

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    log_files = {
        "acp": os.path.join(project_root, "acp_server", "logs", "agent_server.log"),
        "api": os.path.join(project_root, "logos_api", "logs", "logos_api.log"),
        "web": os.path.join(project_root, "logos_web", "logs", "logos_web.log"),
    }

    if service != "all":
        log_files = {k: v for k, v in log_files.items() if k == service}

    result = {}
    for svc, filepath in log_files.items():
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

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    log_paths = {
        "acp": os.path.join(project_root, "acp_server", "logs", "agent_server.log"),
        "api": os.path.join(project_root, "logos_api", "logs", "logos_api.log"),
        "web": os.path.join(project_root, "logos_web", "logs", "logos_web.log"),
    }

    async def event_generator():
        import json

        files = {}
        for svc, filepath in log_paths.items():
            if os.path.exists(filepath):
                f = open(filepath, "r", encoding="utf-8", errors="ignore")
                # Send last 30 lines as initial batch
                all_lines = f.readlines()
                for line in all_lines[-30:]:
                    stripped = line.rstrip()
                    if stripped:
                        data = json.dumps({"service": svc, "line": stripped})
                        yield f"data: {data}\n\n"
                # Now at end of file, will tail new lines
                files[svc] = f

        try:
            while True:
                has_data = False
                for svc, f in files.items():
                    for _ in range(20):  # Read up to 20 lines per tick
                        line = f.readline()
                        if not line:
                            break
                        has_data = True
                        data = json.dumps({"service": svc, "line": line.rstrip()})
                        yield f"data: {data}\n\n"

                if not has_data:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.2)
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
