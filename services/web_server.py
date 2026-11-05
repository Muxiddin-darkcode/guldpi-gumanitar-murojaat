import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from aiohttp import web
import aiohttp

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E-Murojaat Bot Service</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #1e293b;
      padding: 2.5rem 2rem;
      border-radius: 14px;
      border: 1px solid #334155;
      text-align: center;
      max-width: 460px;
      width: 90%;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .badge {
      display: inline-block;
      background: #10b981;
      color: white;
      padding: 4px 14px;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 1.2rem;
      letter-spacing: 0.5px;
    }
    h1 {
      font-size: 1.6rem;
      margin: 0 0 0.5rem;
      color: #38bdf8;
    }
    p {
      color: #94a3b8;
      font-size: 0.95rem;
      line-height: 1.6;
      margin: 0.5rem 0;
    }
    .status-box {
      margin-top: 1rem;
      padding: 0.75rem;
      background: #0f172a;
      border-radius: 8px;
      font-family: monospace;
      font-size: 0.9rem;
      color: #38bdf8;
    }
    .meta {
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid #334155;
      font-size: 0.8rem;
      color: #64748b;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">● TIZIM ISHLAMOQDA</div>
    <h1>E-MUROJAAT</h1>
    <p>Pedagogika fakulteti murojaatlar boti xizmati uzluksiz faol holatda.</p>
    <div class="status-box">
      UptimeRobot Keep-Alive: 200 OK
    </div>
    <div class="meta">
      Guliston davlat pedagogika instituti | 2026
    </div>
  </div>
</body>
</html>
"""


async def handle_index(request: web.Request) -> web.Response:
    """Handles GET and HEAD on / — returns clean status page for UptimeRobot."""
    accept_header = request.headers.get("Accept", "")
    if "application/json" in accept_header:
        return web.json_response({
            "status": "ok",
            "service": "E-MUROJAAT Telegram Bot",
            "bot": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_robot": "200 OK"
        })
    return web.Response(text=HTML_TEMPLATE, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    """Handles GET and HEAD on /health and /ping."""
    return web.json_response({
        "status": "healthy",
        "service": "E-MUROJAAT",
        "bot": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


def create_web_app() -> web.Application:
    """Creates the aiohttp web application for health checks and UptimeRobot."""
    app = web.Application()
    # Note: add_get automatically handles HEAD requests as well in aiohttp
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/ping", handle_health)
    return app


async def start_web_server(host: str = "0.0.0.0", port: int = 8080) -> web.AppRunner:
    """Starts the aiohttp web server on given host and port."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner


async def run_self_ping(url: str, interval_minutes: int = 10) -> None:
    """
    Background keep-alive task: sends an HTTP GET request to url every interval_minutes.
    Guarantees the application stays awake even if UptimeRobot experiences delays.
    """
    if not url:
        return
        
    logger.info(f"Starting self-ping background task for URL: {url} (interval: {interval_minutes}m)")
    delay_seconds = max(60, interval_minutes * 60)
    
    # Wait 30 seconds after bot boot before the first self-ping
    await asyncio.sleep(30)
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    logger.debug(f"Self-ping to {url} returned status: {resp.status}")
            except Exception as e:
                logger.warning(f"Self-ping to {url} failed: {e}")
            await asyncio.sleep(delay_seconds)
