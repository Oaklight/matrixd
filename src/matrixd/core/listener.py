"""Matrix /sync listener with policy-based event filtering.

Long-running async loop that polls /sync, extracts relevant events,
applies per-room policy, and yields filtered events for delivery.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .client import MatrixClient
from .policy import Event, Policy, RoomPolicy

logger = logging.getLogger(__name__)


@dataclass
class ListenerConfig:
    """Listener configuration."""

    # Per-room policy overrides. Key is room_id, value is policy name.
    room_policies: dict[str, RoomPolicy] = field(default_factory=dict)
    # Default policy for rooms not explicitly configured.
    default_policy: RoomPolicy = RoomPolicy.LURK
    # Number of context messages to include with each event.
    context_messages: int = 0
    # Sync timeout in milliseconds (long-poll duration).
    sync_timeout_ms: int = 30000
    # Retry delay on error (seconds).
    error_retry_delay: float = 5.0
    # Maximum retry delay (seconds, for exponential backoff).
    max_retry_delay: float = 300.0


class Listener:
    """Matrix /sync listener with policy filtering.

    Usage:
        async with MatrixClient(...) as client:
            listener = Listener(client, config)
            async for event in listener.listen():
                await deliver(event)
    """

    def __init__(self, client: MatrixClient, config: ListenerConfig) -> None:
        self.client = client
        self.config = config
        self._since: str | None = None
        self._my_user_id: str | None = None
        self._policy = Policy(
            room_policies=config.room_policies,
            default_policy=config.default_policy,
        )

    async def listen(self) -> AsyncIterator[Event]:
        """Infinite async generator yielding filtered Matrix events."""
        # Identify ourselves for anti-echo
        whoami = await self.client.whoami()
        self._my_user_id = whoami["user_id"]
        logger.info("Listener started as %s", self._my_user_id)

        retry_delay = self.config.error_retry_delay

        while True:
            try:
                sync_data = await self.client.sync(
                    since=self._since,
                    timeout_ms=self.config.sync_timeout_ms,
                )
                self._since = sync_data.get("next_batch")
                retry_delay = self.config.error_retry_delay  # reset on success

                for event in self._extract_events(sync_data):
                    if self._policy.should_deliver(event, self._my_user_id):
                        yield event

            except Exception:
                logger.exception("Sync error, retrying in %.1fs", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, self.config.max_retry_delay)

    def _extract_events(self, sync_data: dict[str, Any]) -> list[Event]:
        """Extract message events from sync response."""
        events: list[Event] = []
        rooms = sync_data.get("rooms", {}).get("join", {})

        for room_id, room_data in rooms.items():
            timeline = room_data.get("timeline", {})
            for raw in timeline.get("events", []):
                event = Event.from_sync(room_id, raw)
                if event is not None:
                    events.append(event)

        return events

    async def do_initial_sync(self) -> None:
        """Run one sync to establish the since token, discarding events.

        Call this before listen() to avoid processing historical messages
        on first startup.
        """
        whoami = await self.client.whoami()
        self._my_user_id = whoami["user_id"]
        sync_data = await self.client.sync(timeout_ms=0)
        self._since = sync_data.get("next_batch")
        logger.info("Initial sync complete, since=%s", self._since)
