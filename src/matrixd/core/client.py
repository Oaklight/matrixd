"""Matrix Client-Server API wrapper.

Async HTTP client for the standard Matrix Client-Server API.
Uses only Python stdlib (urllib.request + asyncio executor).
"""

from __future__ import annotations

import asyncio
import http.client
import json
import ssl
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Any
from urllib.parse import quote, urlencode, urlparse


@dataclass
class MatrixClient:
    """Async Matrix Client-Server API client (stdlib only).

    Args:
        homeserver: Base URL of the homeserver (e.g., "https://matrix.example.com").
        token: Access token for authentication.
        timeout: Default request timeout in seconds.
    """

    homeserver: str
    token: str
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.homeserver = self.homeserver.rstrip("/")
        parsed = urlparse(self.homeserver)
        self._scheme = parsed.scheme
        self._host = parsed.hostname or ""
        self._port = parsed.port
        self._base_path = "/_matrix/client/v3"

    async def close(self) -> None:
        pass  # stdlib connections are per-request

    async def __aenter__(self) -> MatrixClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── HTTP layer ────────────────────────────────────────────

    def _request_sync(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Synchronous HTTP request using stdlib."""
        full_path = self._base_path + path
        if params:
            qs = urlencode({k: v for k, v in params.items() if v is not None})
            full_path = f"{full_path}?{qs}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        data = json.dumps(body).encode() if body is not None else None
        effective_timeout = timeout or self.timeout

        if self._scheme == "https":
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                self._host, self._port, timeout=effective_timeout, context=ctx
            )
        else:
            conn = http.client.HTTPConnection(
                self._host, self._port, timeout=effective_timeout
            )

        try:
            conn.request(method, full_path, body=data, headers=headers)
            resp = conn.getresponse()
            resp_data = resp.read().decode()

            if resp.status >= 400:
                raise MatrixAPIError(resp.status, resp_data)

            return json.loads(resp_data) if resp_data else {}
        finally:
            conn.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Async wrapper: runs sync request in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self._request_sync,
                method,
                path,
                body=body,
                params=params,
                timeout=timeout,
            ),
        )

    # ── Identity ──────────────────────────────────────────────

    async def whoami(self) -> dict[str, Any]:
        return await self._request("GET", "/account/whoami")

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
        return await self._request(
            "PUT",
            f"/rooms/{_enc(room_id)}/send/m.room.message/{txn_id}",
            body=content,
        )

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
        return await self._request(
            "PUT",
            f"/rooms/{_enc(room_id)}/send/m.reaction/{txn_id}",
            body=content,
        )

    async def redact(
        self, room_id: str, event_id: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        """Redact (delete) an event."""
        txn_id = f"redact-{int(time.time() * 1e9)}"
        body = {"reason": reason} if reason else {}
        return await self._request(
            "PUT",
            f"/rooms/{_enc(room_id)}/redact/{_enc(event_id)}/{txn_id}",
            body=body,
        )

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
        params: dict[str, Any] = {"dir": direction, "limit": str(limit)}
        if from_token:
            params["from"] = from_token
        if filter_types:
            params["filter"] = json.dumps({"types": filter_types})
        return await self._request(
            "GET", f"/rooms/{_enc(room_id)}/messages", params=params
        )

    async def get_event(self, room_id: str, event_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/rooms/{_enc(room_id)}/event/{_enc(event_id)}"
        )

    # ── Rooms ─────────────────────────────────────────────────

    async def joined_rooms(self) -> list[str]:
        data = await self._request("GET", "/joined_rooms")
        return data.get("joined_rooms", [])

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
            "initial_state": [],
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
        return await self._request("POST", "/createRoom", body=body)

    # ── Membership ────────────────────────────────────────────

    async def invite(self, room_id: str, user_id: str) -> None:
        await self._request(
            "POST", f"/rooms/{_enc(room_id)}/invite", body={"user_id": user_id}
        )

    async def kick(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        await self._request("POST", f"/rooms/{_enc(room_id)}/kick", body=body)

    async def ban(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        await self._request("POST", f"/rooms/{_enc(room_id)}/ban", body=body)

    async def get_members(self, room_id: str) -> list[str]:
        data = await self._request(
            "GET", f"/rooms/{_enc(room_id)}/joined_members"
        )
        return list(data.get("joined", {}).keys())

    # ── State ─────────────────────────────────────────────────

    async def get_state(
        self, room_id: str, event_type: str, state_key: str = ""
    ) -> dict[str, Any]:
        return await self._request(
            "GET", f"/rooms/{_enc(room_id)}/state/{event_type}/{state_key}"
        )

    async def set_state(
        self,
        room_id: str,
        event_type: str,
        content: dict[str, Any],
        state_key: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "PUT",
            f"/rooms/{_enc(room_id)}/state/{event_type}/{state_key}",
            body=content,
        )

    async def get_room_name(self, room_id: str) -> str | None:
        try:
            data = await self.get_state(room_id, "m.room.name")
            return data.get("name")
        except MatrixAPIError:
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
        params: dict[str, Any] = {"timeout": str(timeout_ms)}
        if since:
            params["since"] = since
        if filter_str:
            params["filter"] = filter_str
        return await self._request(
            "GET",
            "/sync",
            params=params,
            timeout=self.timeout + timeout_ms / 1000 + 5,
        )

    # ── Profile ───────────────────────────────────────────────

    async def get_display_name(self, user_id: str) -> str | None:
        try:
            data = await self._request(
                "GET", f"/profile/{_enc(user_id)}/displayname"
            )
            return data.get("displayname")
        except MatrixAPIError as e:
            if e.status == 404:
                return None
            raise


class MatrixAPIError(Exception):
    """Raised when the Matrix API returns an error status."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        try:
            data = json.loads(body)
            self.errcode = data.get("errcode", "")
            self.error = data.get("error", "")
        except (json.JSONDecodeError, KeyError):
            self.errcode = ""
            self.error = body[:200]
        super().__init__(f"HTTP {status}: {self.errcode} {self.error}")


def _enc(value: str) -> str:
    """URL-encode a Matrix identifier for use in URL paths."""
    return quote(value, safe="")
