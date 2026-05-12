"""
WebSocket broadcast server.

Runs in a background daemon thread — does not block the main process.
Call broadcast(data_dict) from any thread to push JSON to all connected browsers.

Hardened against common local-dev failures:
  - origins=None     : allows file:// pages (Origin: null) and any other origin
  - host=127.0.0.1   : loopback only — bypasses Windows Firewall entirely
  - compression=None : avoids deflate negotiation issues in some browsers
  - ping keepalive   : drops stale connections before they pile up
  - OSError guard    : clear message if the port is already in use
"""

import asyncio
import json
import threading
import websockets
from websockets.legacy.server import serve


# CORS headers added to every HTTP-upgrade response so browsers never block.
_CORS_HEADERS = [
    ("Access-Control-Allow-Origin",  "*"),
    ("Access-Control-Allow-Headers", "*"),
    ("Access-Control-Allow-Methods", "GET"),
]


class WsServer:

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self._host    = host
        self._port    = port
        self._clients: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the server in a background daemon thread."""
        t = threading.Thread(target=self._run, daemon=True, name="ws-server")
        t.start()
        print(f"WebSocket server listening on ws://{self._host}:{self._port}")

    def broadcast(self, data: dict) -> None:
        """Thread-safe broadcast — safe to call from any thread."""
        if not self._loop or not self._clients:
            return
        msg = json.dumps(data)
        asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    # ── internals ─────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except OSError as e:
            print(f"[WsServer] ERROR: could not bind to port {self._port} — {e}")
            print(f"[WsServer] Is another process already using port {self._port}?")

    async def _serve(self) -> None:
        async with serve(
            self._handler,
            self._host,
            self._port,
            origins      = None,          # allow all origins incl. file:// (Origin: null)
            compression  = None,          # disable deflate — avoids browser compat issues
            extra_headers= _CORS_HEADERS, # CORS headers on the HTTP-101 upgrade response
            ping_interval= 20,            # keepalive ping every 20 s
            ping_timeout = 10,            # drop if no pong within 10 s
        ):
            await asyncio.Future()        # run forever

    async def _handler(self, ws) -> None:
        self._clients.add(ws)
        print(f"[WsServer] client connected    — {len(self._clients)} total")
        try:
            await ws.wait_closed()
        finally:
            self._clients.discard(ws)
            print(f"[WsServer] client disconnected — {len(self._clients)} remaining")

    async def _broadcast(self, msg: str) -> None:
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead
