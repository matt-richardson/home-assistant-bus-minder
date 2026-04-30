from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from collections.abc import AsyncIterator, Callable
from typing import Optional

import aiohttp

from .const import LIVE_BASE_URL, SIGNALR_HEADERS
from .models import BusPosition

_LOGGER = logging.getLogger(__name__)

_CONNECTION_DATA = '[{"name":"broadcasthub"}]'


class SignalRClient:
    """Async SignalR 2.x client using Server-Sent Events transport."""

    def __init__(self, session: aiohttp.ClientSession, route_uuid: str) -> None:
        self._session = session
        self._route_uuid = route_uuid.lower()

    def _qs(self, token: str) -> dict:
        return {
            "transport": "serverSentEvents",
            "clientProtocol": "2.0",
            "connectionToken": token,
            "connectionData": _CONNECTION_DATA,
        }

    async def _negotiate(self) -> tuple[str, float]:
        """Negotiate a connection token. Returns (token, keepalive_timeout_s)."""
        async with self._session.get(
            f"{LIVE_BASE_URL}/negotiate",
            params={"clientProtocol": "2.0", "connectionData": _CONNECTION_DATA},
            headers=SIGNALR_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return data["ConnectionToken"], float(data.get("KeepAliveTimeout", 20.0))

    async def _start(self, token: str) -> None:
        async with self._session.get(
            f"{LIVE_BASE_URL}/start",
            params=self._qs(token),
            headers=SIGNALR_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()

    async def _register(self, token: str) -> None:
        msg = json.dumps(
            {"H": "broadcasthub", "M": "Register", "A": [self._route_uuid], "I": 0},
            separators=(",", ":"),
        )
        body = "data=" + urllib.parse.quote(msg)
        async with self._session.post(
            f"{LIVE_BASE_URL}/send",
            params=self._qs(token),
            data=body,
            headers={
                **SIGNALR_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()

    def _parse_sse_payload(self, payload: str) -> list[BusPosition]:
        """Parse a single SSE data payload into a list of BusPosition objects."""
        if not payload or payload == "{}":
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        positions = []
        for msg in data.get("M", []):
            if msg.get("M") != "gps":
                continue
            args = msg.get("A", [])
            if not args:
                continue
            try:
                pos = BusPosition.from_gps_args(args[0])
                positions.append(pos)
            except (KeyError, ValueError, TypeError) as exc:
                _LOGGER.debug("Failed to parse GPS message: %s", exc)
        return positions

    async def stream(self, on_connected: Optional[Callable[[], None]] = None) -> AsyncIterator[BusPosition]:
        """
        Connect to BusMinder SignalR and yield BusPosition updates indefinitely.
        Handles the full negotiation + SSE open + start + register sequence.

        IMPORTANT: The server requires the SSE /connect stream to be open and
        actively read before it will accept the /start and /register POST.
        We read until "initialized", sleep 2s, then send start + register inline.
        """
        token, keepalive_s = await self._negotiate()
        qs = self._qs(token)
        # Allow 3× the server's keepalive interval before declaring the connection
        # stale. The server sends {} every keepalive_s seconds, so genuine silence
        # beyond that means the TCP connection is dead (e.g. after laptop sleep).
        sock_read_timeout = keepalive_s * 3

        async with self._session.get(
            f"{LIVE_BASE_URL}/connect",
            params=qs,
            headers={**SIGNALR_HEADERS, "Accept": "text/event-stream"},
            timeout=aiohttp.ClientTimeout(total=None, sock_read=sock_read_timeout),
        ) as resp:
            resp.raise_for_status()
            initialized = False
            async for raw_line in resp.content:
                line = raw_line.decode(errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()

                if payload == "initialized" and not initialized:
                    initialized = True
                    # Server needs ~2s to fully register the SSE connection
                    # before it will accept /start and /register requests.
                    await asyncio.sleep(2)
                    await self._start(token)
                    await self._register(token)
                    if on_connected is not None:
                        on_connected()
                    continue

                for pos in self._parse_sse_payload(payload):
                    yield pos
