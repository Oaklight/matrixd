"""Matrix Client-Server API wrapper.

Async HTTP client for the standard Matrix Client-Server API.
Uses zerodep's httpclient (vendored, stdlib-only).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .._vendor.httpclient import AsyncClient, Response


class MatrixAPIError(Exception):
    """Error from the Matrix Client-Server API.

    Attributes:
        status_code: HTTP status code.
        errcode: Matrix error code (e.g., ``M_FORBIDDEN``, ``M_NOT_FOUND``).
        error: Human-readable error message from the server.
        body: Full response body dict.
    """

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.errcode: str = body.get("errcode", "M_UNKNOWN")
        self.error: str = body.get("error", "Unknown error")
        self.body = body
        super().__init__(f"[{self.status_code}] {self.errcode}: {self.error}")


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

    def __post_init__(self) -> None:
        self.homeserver = self.homeserver.rstrip("/")
        self._base = f"{self.homeserver}/_matrix/client/v3"
        self._http = AsyncClient(
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> MatrixClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── HTTP helpers ──────────────────────────────────────────

    def _check(self, resp: Response) -> Response:
        """Raise MatrixAPIError on non-2xx responses."""
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text[:500]}
            raise MatrixAPIError(resp.status_code, body)
        return resp

    async def _get(
        self, path: str, *, params: dict[str, Any] | None = None, timeout: float | None = None,
    ) -> Response:
        resp = await self._http.get(
            f"{self._base}{path}", params=params, **({"timeout": timeout} if timeout else {}),
        )
        return self._check(resp)

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> Response:
        resp = await self._http.post(f"{self._base}{path}", json=body or {})
        return self._check(resp)

    async def _put(self, path: str, body: dict[str, Any] | None = None) -> Response:
        resp = await self._http.put(f"{self._base}{path}", json=body or {})
        return self._check(resp)

    # ── Identity ──────────────────────────────────────────────

    async def whoami(self) -> dict[str, Any]:
        return (await self._get("/account/whoami")).json()

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
        return (
            await self._put(
                f"/rooms/{_enc(room_id)}/send/m.room.message/{txn_id}", content
            )
        ).json()

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
        return (
            await self._put(
                f"/rooms/{_enc(room_id)}/send/m.reaction/{txn_id}", content
            )
        ).json()

    async def redact(
        self, room_id: str, event_id: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        """Redact (delete) an event."""
        txn_id = f"redact-{int(time.time() * 1e9)}"
        body = {"reason": reason} if reason else {}
        return (
            await self._put(
                f"/rooms/{_enc(room_id)}/redact/{_enc(event_id)}/{txn_id}", body
            )
        ).json()

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
        import json as _json

        params: dict[str, Any] = {"dir": direction, "limit": limit}
        if from_token:
            params["from"] = from_token
        if filter_types:
            params["filter"] = _json.dumps({"types": filter_types})
        return (await self._get(f"/rooms/{_enc(room_id)}/messages", params=params)).json()

    async def get_event(self, room_id: str, event_id: str) -> dict[str, Any]:
        return (
            await self._get(f"/rooms/{_enc(room_id)}/event/{_enc(event_id)}")
        ).json()

    # ── Rooms ─────────────────────────────────────────────────

    async def joined_rooms(self) -> list[str]:
        return (await self._get("/joined_rooms")).json().get("joined_rooms", [])

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
        return (await self._post("/createRoom", body)).json()

    # ── Membership ────────────────────────────────────────────

    async def invite(self, room_id: str, user_id: str) -> None:
        await self._post(f"/rooms/{_enc(room_id)}/invite", {"user_id": user_id})

    async def kick(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        await self._post(f"/rooms/{_enc(room_id)}/kick", body)

    async def ban(
        self, room_id: str, user_id: str, *, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"user_id": user_id}
        if reason:
            body["reason"] = reason
        await self._post(f"/rooms/{_enc(room_id)}/ban", body)

    async def get_members(self, room_id: str) -> list[str]:
        return list(
            (await self._get(f"/rooms/{_enc(room_id)}/joined_members"))
            .json()
            .get("joined", {})
            .keys()
        )

    # ── State ─────────────────────────────────────────────────

    async def get_state(
        self, room_id: str, event_type: str, state_key: str = ""
    ) -> dict[str, Any]:
        return (
            await self._get(f"/rooms/{_enc(room_id)}/state/{event_type}/{state_key}")
        ).json()

    async def set_state(
        self,
        room_id: str,
        event_type: str,
        content: dict[str, Any],
        state_key: str = "",
    ) -> dict[str, Any]:
        return (
            await self._put(
                f"/rooms/{_enc(room_id)}/state/{event_type}/{state_key}", content
            )
        ).json()

    async def get_room_name(self, room_id: str) -> str | None:
        try:
            data = await self.get_state(room_id, "m.room.name")
            return data.get("name")
        except Exception:
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
        return (
            await self._get(
                "/sync",
                params=params,
                timeout=self.timeout + timeout_ms / 1000 + 5,
            )
        ).json()

    # ── Profile ───────────────────────────────────────────────

    async def get_display_name(self, user_id: str) -> str | None:
        try:
            return (
                await self._get(f"/profile/{_enc(user_id)}/displayname")
            ).json().get("displayname")
        except Exception:
            return None


def _enc(value: str) -> str:
    """URL-encode a Matrix identifier for use in URL paths."""
    return quote(value, safe="")
