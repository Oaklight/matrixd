"""Webhook delivery — POST events to an HTTP endpoint (stdlib only)."""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import ssl
from functools import partial
from typing import Any
from urllib.parse import urlparse

from ..core.policy import Event
from .base import DeliveryBackend

logger = logging.getLogger(__name__)


class WebhookDelivery(DeliveryBackend):
    def __init__(self, url: str, *, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout
        parsed = urlparse(url)
        self._scheme = parsed.scheme
        self._host = parsed.hostname or ""
        self._port = parsed.port
        self._path = parsed.path or "/"
        if parsed.query:
            self._path += f"?{parsed.query}"

    def _post_sync(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "Content-Length": str(len(data))}

        if self._scheme == "https":
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                self._host, self._port, timeout=self.timeout, context=ctx
            )
        else:
            conn = http.client.HTTPConnection(
                self._host, self._port, timeout=self.timeout
            )

        try:
            conn.request("POST", self._path, body=data, headers=headers)
            resp = conn.getresponse()
            if resp.status >= 400:
                body = resp.read().decode()[:200]
                logger.warning(
                    "Webhook %s returned %d: %s", self.url, resp.status, body
                )
        finally:
            conn.close()

    async def deliver(self, event: Event) -> None:
        payload = json.loads(self.serialize(event, "json"))
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, partial(self._post_sync, payload))
        except Exception:
            logger.exception("Webhook delivery to %s failed", self.url)
