"""MCP tool server for Matrix operations.

Exposes Matrix Client-Server API operations as MCP tools.
Supports stdio, SSE, and Streamable HTTP transports.

Usage:
    matrixd serve --mode mcp                           # stdio (default)
    matrixd serve --mode mcp --transport sse            # SSE
    matrixd serve --mode mcp --transport streamable-http # Streamable HTTP
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.session import ServerSession

from ..core.client import MatrixAPIError, MatrixClient
from ..core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Lifespan context holding the Matrix client."""

    client: MatrixClient
    config: Config


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage Matrix client lifecycle."""
    from ..core.config import load_config

    config = load_config()
    client = MatrixClient(
        homeserver=config.homeserver,
        token=config.resolve_token(),
    )
    try:
        # Verify credentials on startup
        whoami = await client.whoami()
        logger.info("MCP server connected as %s", whoami.get("user_id"))
        yield AppContext(client=client, config=config)
    finally:
        await client.close()


def _get_client(ctx: Context[ServerSession, AppContext]) -> MatrixClient:
    """Extract Matrix client from MCP context."""
    return ctx.request_context.lifespan_context.client


# ── Server instance ───────────────────────────────────────────

mcp_server = FastMCP(
    "matrixd",
    instructions=(
        "Matrix operations server. Use these tools to interact with Matrix "
        "rooms: send messages, read history, manage rooms and members, "
        "and query room state."
    ),
    lifespan=app_lifespan,
)


# ── Tools: Identity ──────────────────────────────────────────

@mcp_server.tool()
async def whoami(ctx: Context[ServerSession, AppContext]) -> dict[str, Any]:
    """Verify Matrix credentials and return the authenticated user ID and device ID."""
    try:
        return await _get_client(ctx).whoami()
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: Messaging ─────────────────────────────────────────

@mcp_server.tool()
async def send_message(
    room_id: str,
    body: str,
    ctx: Context[ServerSession, AppContext],
    msgtype: str = "m.text",
    formatted_body: str | None = None,
) -> dict[str, Any]:
    """Send a text message to a Matrix room.

    Args:
        room_id: Target room ID (e.g., "!abc123:server").
        body: Message text content.
        msgtype: Message type (default: "m.text"). Other options: "m.notice", "m.emote".
        formatted_body: Optional HTML-formatted body for rich messages.
    """
    try:
        return await _get_client(ctx).send_message(
            room_id, body, msgtype=msgtype, formatted_body=formatted_body,
        )
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def send_reaction(
    room_id: str,
    event_id: str,
    emoji: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, Any]:
    """React to a message with an emoji.

    Args:
        room_id: Room containing the target event.
        event_id: Event ID to react to (e.g., "$xyz789").
        emoji: Emoji reaction (e.g., "👍", "❤️").
    """
    try:
        return await _get_client(ctx).send_reaction(room_id, event_id, emoji)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def redact_event(
    room_id: str,
    event_id: str,
    ctx: Context[ServerSession, AppContext],
    reason: str | None = None,
) -> dict[str, Any]:
    """Delete (redact) a message or event.

    Args:
        room_id: Room containing the event.
        event_id: Event ID to redact.
        reason: Optional reason for redaction.
    """
    try:
        return await _get_client(ctx).redact(room_id, event_id, reason=reason)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: History ───────────────────────────────────────────

@mcp_server.tool()
async def get_messages(
    room_id: str,
    ctx: Context[ServerSession, AppContext],
    limit: int = 20,
    direction: str = "b",
) -> dict[str, Any]:
    """Read room message history.

    Args:
        room_id: Room to read history from.
        limit: Maximum number of events to return (default: 20).
        direction: "b" for backward (newest first), "f" for forward (oldest first).
    """
    try:
        return await _get_client(ctx).get_messages(
            room_id, limit=limit, direction=direction,
        )
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def get_event(
    room_id: str,
    event_id: str,
    ctx: Context[ServerSession, AppContext],
) -> dict[str, Any]:
    """Retrieve a single event by ID.

    Args:
        room_id: Room containing the event.
        event_id: Event ID to retrieve.
    """
    try:
        return await _get_client(ctx).get_event(room_id, event_id)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: Rooms ─────────────────────────────────────────────

@mcp_server.tool()
async def list_rooms(
    ctx: Context[ServerSession, AppContext],
) -> list[dict[str, str | None]]:
    """List all joined rooms with their names.

    Returns a list of objects with room_id and name fields.
    """
    try:
        client = _get_client(ctx)
        room_ids = await client.joined_rooms()
        results = []
        for rid in room_ids:
            name = await client.get_room_name(rid)
            results.append({"room_id": rid, "name": name})
        return results
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def create_room(
    ctx: Context[ServerSession, AppContext],
    name: str | None = None,
    topic: str | None = None,
    preset: str = "private_chat",
    invite: str | None = None,
) -> dict[str, Any]:
    """Create a new Matrix room.

    Args:
        name: Room display name.
        topic: Room topic description.
        preset: Room preset — "private_chat", "public_chat", or "trusted_private_chat".
        invite: Comma-separated user IDs to invite (e.g., "@alice:server,@bob:server").
    """
    invite_list = [u.strip() for u in invite.split(",")] if invite else None
    try:
        return await _get_client(ctx).create_room(
            name=name, topic=topic, preset=preset, invite=invite_list,
        )
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: Membership ────────────────────────────────────────

@mcp_server.tool()
async def invite_user(
    room_id: str,
    user_id: str,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Invite a user to a room.

    Args:
        room_id: Room to invite to.
        user_id: User ID to invite (e.g., "@alice:server").
    """
    try:
        await _get_client(ctx).invite(room_id, user_id)
        return f"Invited {user_id} to {room_id}"
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def kick_user(
    room_id: str,
    user_id: str,
    ctx: Context[ServerSession, AppContext],
    reason: str | None = None,
) -> str:
    """Kick a user from a room.

    Args:
        room_id: Room to kick from.
        user_id: User ID to kick.
        reason: Optional reason.
    """
    try:
        await _get_client(ctx).kick(room_id, user_id, reason=reason)
        return f"Kicked {user_id} from {room_id}"
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def get_members(
    room_id: str,
    ctx: Context[ServerSession, AppContext],
) -> list[str]:
    """List all members of a room.

    Args:
        room_id: Room to query.
    """
    try:
        return await _get_client(ctx).get_members(room_id)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: State ─────────────────────────────────────────────

@mcp_server.tool()
async def get_room_state(
    room_id: str,
    event_type: str,
    ctx: Context[ServerSession, AppContext],
    state_key: str = "",
) -> dict[str, Any]:
    """Read room state (e.g., power levels, room name, topic).

    Args:
        room_id: Room to query.
        event_type: State event type (e.g., "m.room.power_levels", "m.room.name").
        state_key: State key (usually empty string).
    """
    try:
        return await _get_client(ctx).get_state(room_id, event_type, state_key)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def set_room_state(
    room_id: str,
    event_type: str,
    content: str,
    ctx: Context[ServerSession, AppContext],
    state_key: str = "",
) -> dict[str, Any]:
    """Set room state (e.g., update power levels, room name).

    Args:
        room_id: Room to modify.
        event_type: State event type.
        content: JSON string of the state content.
        state_key: State key (usually empty string).
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ToolError(f"Invalid JSON content: {e}") from e
    try:
        return await _get_client(ctx).set_state(room_id, event_type, parsed, state_key)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


@mcp_server.tool()
async def set_power_level(
    room_id: str,
    user_id: str,
    level: int,
    ctx: Context[ServerSession, AppContext],
) -> str:
    """Set a user's power level in a room.

    Args:
        room_id: Room to modify.
        user_id: User whose power level to set.
        level: Power level (0=default, 50=moderator, 100=admin).
    """
    try:
        await _get_client(ctx).set_user_power_level(room_id, user_id, level)
        return f"Set {user_id} power level to {level} in {room_id}"
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Tools: Profile ───────────────────────────────────────────

@mcp_server.tool()
async def get_display_name(
    user_id: str,
    ctx: Context[ServerSession, AppContext],
) -> str | None:
    """Get a user's display name.

    Args:
        user_id: User ID to look up (e.g., "@alice:server").
    """
    try:
        return await _get_client(ctx).get_display_name(user_id)
    except MatrixAPIError as e:
        raise ToolError(str(e)) from e


# ── Run ──────────────────────────────────────────────────────

def run_mcp_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8989,
) -> None:
    """Start the MCP server with the specified transport.

    Args:
        transport: Transport mode — "stdio", "sse", or "streamable-http".
        host: Bind host for SSE/HTTP transports.
        port: Bind port for SSE/HTTP transports.
    """
    mcp_server.run(transport=transport, host=host, port=port)
