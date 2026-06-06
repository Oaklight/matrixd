"""Webhook delivery — POST events to an HTTP endpoint.

Uses zerodep's httpclient (vendored, async).
"""

from __future__ import annotations

import json
import logging

from ..core.policy import Event
from ..vendor.httpclient import AsyncClient
from .base import DeliveryBackend

logger = logging.getLogger(__name__)


class WebhookDelivery(DeliveryBackend):
    def __init__(self, url: str, *, timeout: float = 10.0) -> None:
        self.url = url
        self._http = AsyncClient(timeout=timeout)

    async def deliver(self, event: Event) -> None:
        payload = json.loads(self.serialize(event, "json"))
        try:
            resp = await self._http.post(self.url, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "Webhook %s returned %d: %s",
                    self.url,
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception:
            logger.exception("Webhook delivery to %s failed", self.url)

    async def close(self) -> None:
        await self._http.aclose()
