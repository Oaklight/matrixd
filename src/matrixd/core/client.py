"""Matrix Client-Server API wrapper.

Async HTTP client for the standard Matrix Client-Server API.
Replaces curl+jq with a proper Python interface — same endpoints,
same semantics, typed responses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class MatrixClient:
    """Async Matrix Client-Server API client.

    Args:
        homeserver: Base URL of the homeserver (e.g., "https://matrix.example.com").
        token: Access token for authentication.
        timeout: Default request timeout in seconds.
    """

    homeserver: str
    token: str
    timeout: float = 30.0
    _http: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.homeserver = self.homeserver.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=f"{self.homeserver}/_matrix/client/v3",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> MatrixClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── Identity ──────────────────────────────────────────────

    async def whoami(self) -> dict[str, Any]:
        resp = await self._http.get("/account/whoami")
        resp.raise_for_status()
        return resp.json()

    # ── Messaging ─────────────────────────────────────────────

    async def send_message(
        self,
        room_id: str,
        body: str,
        *,
        msgtype: str = "m.text",
        formatted_body: str | None = None,
    ) -> dict[str, Any]:
        """Send a message to a room."""
        txn_id = f"matrixd-{int(time.time() * 1e9)}"
        content: dict[str, Any] = {"msgtype": msgtype, "body": body}
        if formatted_body:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = formatted_body
        resp = await self._http.put(
            f"/rooms/{_encode(room_id)}/send/m.room.message/{txn_id}",
            json=content,
        )
        resp.raise_for_status()
        return resp.json()

    async def send_reaction(
        self, room_id: str, event_id: str, emoji: str
    ) -> dict[str, Any]:
        """Send a reaction to an event."""
        txn_id = f"react-{int(time.time() * 1e9)}"
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": emoji,
            }
        }
        resp = await self._http.put(
            f"/rooms/{_encode(room_id)}/send/m.reaction/{txn_id}",
            json=content,
        )
        resp.raise_for_status()
        return resp.json()

    async def redact(
        self, room_id: str, event_id: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        """Redact (delete) an event."""
        txn_id = f"redact-{int(time.time() * 1e9)}"
        body = {"reason": reason} if reason else {}
        resp = await self._http.put(
            f"/rooms/{_encode(room_id)}/redact/{_encode(event_id)}/{txn_id}",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    # ── History ───────────────────────────────────────────────

    async def get_messages(
        self,
        room_id: str,
        *,
        limit: int = 20,
        direction: str = "b",
        from_token: str | None = None,
        filter_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Read room message history."""
        params: dict[str, Any] = {"dir": direction, "limit": limit}
        if from_token:
            params["from"] = from_token
        if filter_types:
            import json

            params["filter"] = json.dumps({"types": filter_types})
        resp = await self._http.get(f"/rooms/{_encode(room_id)}/messages", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_event(self, room_id: str, event_id: str) -> dict[str, Any]:
        resp = await self._http.get(
            f"/rooms/{_encode(room_id)}/event/{_encode(event_id)}"
        )
        resp.raise_for_status()
        return resp.json()

    # ── Rooms ─────────────────────────────────────────────────

    async def joined_rooms(self) -> list[str]:
        resp = await self._http.get("/joined_rooms")
        resp.raise_for_status()
        return resp.json().get("joined_rooms", [])

    async def create_room(
        self,
        *,
        name: str | None = None,
        topic: str | None = None,
        preset: str = "private_chat",
        invite: list[str] | None = None,
        power_level_overrides: dict[str, int] | None = None,
        is_direct: bool = False,
    ) -> dict[str, Any]:
        """Create a new room."""
        body: dict[str, Any] = {
            "preset": preset,
            "visibility": "private",
            "initial_state": [],  # explicit: no encryption
        }
        if name:
            body["name"] = name
        if topic:
            body["topic"] = topic
        if invite:
            body["invite"] = invite
        if is_direct:
            body["is_direct"] = True
        if power_level_overrides:
            body["power_level_content_override"] = {"users": power_level_overrides}
        resp = await self._http.post("/createRoom", json=body)
        resp.raise_for_status()
        return resp.json()

    # ── Membership ────────────────────────────────────────────

    async def invite(self, room_id: str, user_id: str) -> None:
        resp = await self._http.post(
            f"/rooms/{_encode(room_id)}/invite", json={"user_id": user_id}
        )
        resp.raise_for_status()

    async def kick(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        resp = await self._http.post(f"/rooms/{_encode(room_id)}/kick", json=body)
        resp.raise_for_status()

    async def ban(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        resp = await self._http.post(f"/rooms/{_encode(room_id)}/ban", json=body)
        resp.raise_for_status()

    async def get_members(self, room_id: str) -> list[str]:
        resp = await self._http.get(f"/rooms/{_encode(room_id)}/joined_members")
        resp.raise_for_status()
        return list(resp.json().get("joined", {}).keys())

    # ── State ─────────────────────────────────────────────────

    async def get_state(
        self, room_id: str, event_type: str, state_key: str = ""
    ) -> dict[str, Any]:
        resp = await self._http.get(
            f"/rooms/{_encode(room_id)}/state/{event_type}/{state_key}"
        )
        resp.raise_for_status()
        return resp.json()

    async def set_state(
        self,
        room_id: str,
        event_type: str,
        content: dict[str, Any],
        state_key: str = "",
    ) -> dict[str, Any]:
        resp = await self._http.put(
            f"/rooms/{_encode(room_id)}/state/{event_type}/{state_key}",
            json=content,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_room_name(self, room_id: str) -> str | None:
        try:
            data = await self.get_state(room_id, "m.room.name")
            return data.get("name")
        except httpx.HTTPStatusError:
            return None

    async def set_room_name(self, room_id: str, name: str) -> None:
        await self.set_state(room_id, "m.room.name", {"name": name})

    async def get_power_levels(self, room_id: str) -> dict[str, Any]:
        return await self.get_state(room_id, "m.room.power_levels")

    async def set_user_power_level(
        self, room_id: str, user_id: str, level: int
    ) -> None:
        """Set a single user's power level (read-modify-write)."""
        pl = await self.get_power_levels(room_id)
        pl["users"][user_id] = level
        await self.set_state(room_id, "m.room.power_levels", pl)

    # ── Sync ──────────────────────────────────────────────────

    async def sync(
        self,
        *,
        since: str | None = None,
        timeout_ms: int = 30000,
        filter_str: str | None = None,
    ) -> dict[str, Any]:
        """Long-poll /sync endpoint."""
        params: dict[str, Any] = {"timeout": timeout_ms}
        if since:
            params["since"] = since
        if filter_str:
            params["filter"] = filter_str
        resp = await self._http.get(
            "/sync",
            params=params,
            timeout=self.timeout + timeout_ms / 1000 + 5,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Profile ───────────────────────────────────────────────

    async def get_display_name(self, user_id: str) -> str | None:
        resp = await self._http.get(f"/profile/{_encode(user_id)}/displayname")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("displayname")


def _encode(value: str) -> str:
    """URL-encode a Matrix identifier for use in URL paths."""
    from urllib.parse import quote

    return quote(value, safe="")
