"""Base delivery backend interface."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from ..core.policy import Event


class DeliveryBackend(ABC):
    """Abstract base for event delivery backends."""

    @abstractmethod
    async def deliver(self, event: Event) -> None:
        """Deliver a single filtered event."""

    async def close(self) -> None:
        """Cleanup resources."""

    @staticmethod
    def serialize(event: Event, fmt: str = "json") -> str:
        """Serialize an event for delivery."""
        if fmt == "json":
            return json.dumps(
                {
                    "room_id": event.room_id,
                    "event_id": event.event_id,
                    "sender": event.sender,
                    "type": event.event_type,
                    "body": event.body,
                    "msgtype": event.msgtype,
                    "timestamp": event.origin_server_ts,
                    "content": event.content,
                },
                ensure_ascii=False,
            )
        else:
            # Plain text format
            sender = event.sender.split(":")[0].lstrip("@")
            return f"[{event.room_id}] {sender}: {event.body}"


def create_backend(mode: str, **kwargs: Any) -> DeliveryBackend:
    """Factory for delivery backends."""
    if mode == "stdout":
        from .stdout import StdoutDelivery

        return StdoutDelivery(fmt=kwargs.get("format", "json"))
    elif mode == "webhook":
        from .webhook import WebhookDelivery

        url = kwargs.get("webhook_url")
        if not url:
            raise ValueError("webhook delivery requires 'webhook_url'")
        return WebhookDelivery(url=url)
    elif mode == "exec":
        from .exec_cmd import ExecDelivery

        cmd = kwargs.get("exec_cmd")
        if not cmd:
            raise ValueError("exec delivery requires 'exec_cmd'")
        return ExecDelivery(
            cmd=cmd, fmt=kwargs.get("format", "json"),
            timeout=kwargs.get("exec_timeout", 30.0),
        )
    else:
        raise ValueError(f"Unknown delivery mode: {mode}")
