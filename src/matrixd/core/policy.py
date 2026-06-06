"""Event policy engine.

Determines which events should be delivered based on per-room policies.
Inspired by OpenClaw's lurk/mention routing semantics, generalized
for any agent platform.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class RoomPolicy(enum.Enum):
    """Per-room event delivery policy."""

    LURK = "lurk"
    """Ignore all events (monitor only, no delivery)."""

    MENTION_ONLY = "mention-only"
    """Deliver only when the bot is mentioned by name or user ID."""

    ALL = "all"
    """Deliver all message events."""

    IMPORTANT = "important"
    """Deliver mentions + replies to bot's own messages."""


@dataclass
class Event:
    """Normalized Matrix event."""

    room_id: str
    event_id: str
    sender: str
    event_type: str
    content: dict[str, Any]
    origin_server_ts: int
    # Extracted fields for convenience
    body: str = ""
    msgtype: str = ""
    relates_to: dict[str, Any] | None = None

    @classmethod
    def from_sync(cls, room_id: str, raw: dict[str, Any]) -> Event | None:
        """Parse a sync timeline event into an Event, or None if irrelevant."""
        event_type = raw.get("type", "")
        # Only process message events for now
        if event_type not in ("m.room.message", "m.reaction"):
            return None

        content = raw.get("content", {})
        return cls(
            room_id=room_id,
            event_id=raw.get("event_id", ""),
            sender=raw.get("sender", ""),
            event_type=event_type,
            content=content,
            origin_server_ts=raw.get("origin_server_ts", 0),
            body=content.get("body", ""),
            msgtype=content.get("msgtype", ""),
            relates_to=content.get("m.relates_to"),
        )


@dataclass
class Policy:
    """Policy engine that decides which events to deliver."""

    room_policies: dict[str, RoomPolicy] = field(default_factory=dict)
    default_policy: RoomPolicy = RoomPolicy.LURK

    def get_room_policy(self, room_id: str) -> RoomPolicy:
        return self.room_policies.get(room_id, self.default_policy)

    def should_deliver(self, event: Event, my_user_id: str | None = None) -> bool:
        """Decide whether an event should be delivered."""
        # Anti-echo: never deliver our own messages
        if my_user_id and event.sender == my_user_id:
            return False

        policy = self.get_room_policy(event.room_id)

        if policy == RoomPolicy.LURK:
            return False

        if policy == RoomPolicy.ALL:
            return True

        if policy in (RoomPolicy.MENTION_ONLY, RoomPolicy.IMPORTANT):
            if my_user_id and self._is_mentioned(event, my_user_id):
                return True
            if policy == RoomPolicy.IMPORTANT and self._is_reply_to_me(
                event, my_user_id
            ):
                return True
            return False

        return False

    @staticmethod
    def _is_mentioned(event: Event, my_user_id: str) -> bool:
        """Check if the bot is mentioned in the event body."""
        if not event.body:
            return False
        # Check for @user_id mention
        if my_user_id in event.body:
            return True
        # Check for display name mention (extract localpart)
        localpart = my_user_id.split(":")[0].lstrip("@")
        if localpart.lower() in event.body.lower():
            return True
        return False

    @staticmethod
    def _is_reply_to_me(event: Event, my_user_id: str | None) -> bool:
        """Check if the event is a reply to one of the bot's messages."""
        if not my_user_id or not event.relates_to:
            return False
        in_reply_to = event.relates_to.get("m.in_reply_to", {})
        # We'd need to look up the original event to check sender.
        # For now, return False — full implementation needs event cache.
        return False
