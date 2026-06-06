"""REST/OpenAPI server for Matrix operations.

Lightweight HTTP API using stdlib http.server.
Exposes Matrix Client-Server API operations as REST endpoints.

Usage:
    matrixd serve --mode rest
    matrixd serve --mode rest --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from ..core.client import MatrixAPIError, MatrixClient
from ..core.config import Config, load_config

logger = logging.getLogger(__name__)


# ── Route registry ───────────────────────────────────────────

Route = tuple[str, str, str]  # (method, pattern, handler_name)

ROUTES: list[Route] = [
    ("GET",  r"/api/whoami$",                         "handle_whoami"),
    ("GET",  r"/api/rooms$",                          "handle_list_rooms"),
    ("POST", r"/api/rooms$",                          "handle_create_room"),
    ("GET",  r"/api/rooms/(?P<room_id>[^/]+)/messages$", "handle_get_messages"),
    ("POST", r"/api/rooms/(?P<room_id>[^/]+)/send$",     "handle_send_message"),
    ("POST", r"/api/rooms/(?P<room_id>[^/]+)/react$",    "handle_send_reaction"),
    ("POST", r"/api/rooms/(?P<room_id>[^/]+)/redact$",   "handle_redact"),
    ("GET",  r"/api/rooms/(?P<room_id>[^/]+)/members$",  "handle_get_members"),
    ("GET",  r"/api/rooms/(?P<room_id>[^/]+)/state/(?P<event_type>[^/]+)$",
     "handle_get_state"),
    ("PUT",  r"/api/rooms/(?P<room_id>[^/]+)/state/(?P<event_type>[^/]+)$",
     "handle_set_state"),
    ("POST", r"/api/rooms/(?P<room_id>[^/]+)/invite$",  "handle_invite"),
    ("POST", r"/api/rooms/(?P<room_id>[^/]+)/kick$",    "handle_kick"),
    ("PUT",  r"/api/rooms/(?P<room_id>[^/]+)/power-level$",
     "handle_set_power_level"),
    ("GET",  r"/api/profile/(?P<user_id>[^/]+)/displayname$",
     "handle_get_display_name"),
    ("GET",  r"/api/health$",                         "handle_health"),
    ("GET",  r"/openapi\.json$",                      "handle_openapi"),
]


def _build_openapi_spec(host: str, port: int) -> dict[str, Any]:
    """Build a minimal OpenAPI 3.0 spec."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "matrixd REST API",
            "version": "0.1.0",
            "description": "REST API for Matrix Client-Server operations.",
        },
        "servers": [{"url": f"http://{host}:{port}"}],
        "paths": {
            "/api/whoami": {
                "get": {"summary": "Verify credentials", "operationId": "whoami"}
            },
            "/api/rooms": {
                "get": {"summary": "List joined rooms", "operationId": "listRooms"},
                "post": {"summary": "Create a room", "operationId": "createRoom"},
            },
            "/api/rooms/{room_id}/messages": {
                "get": {"summary": "Read room history", "operationId": "getMessages"}
            },
            "/api/rooms/{room_id}/send": {
                "post": {"summary": "Send a message", "operationId": "sendMessage"}
            },
            "/api/rooms/{room_id}/members": {
                "get": {"summary": "List members", "operationId": "getMembers"}
            },
            "/api/rooms/{room_id}/invite": {
                "post": {"summary": "Invite a user", "operationId": "inviteUser"}
            },
            "/api/health": {
                "get": {"summary": "Health check", "operationId": "health"}
            },
        },
    }


class MatrixHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Matrix REST API."""

    client: MatrixClient
    config: Config
    _loop: asyncio.AbstractEventLoop

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info(fmt, *args)

    def _json_response(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, status: int, message: str) -> None:
        self._json_response({"error": message}, status)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _run_async(self, coro: Any) -> Any:
        return self._loop.run_until_complete(coro)

    def _dispatch(self, method: str) -> None:
        from urllib.parse import unquote

        for route_method, pattern, handler_name in ROUTES:
            if route_method != method:
                continue
            match = re.match(pattern, self.path.split("?")[0])
            if match:
                handler = getattr(self, handler_name)
                kwargs = {k: unquote(v) for k, v in match.groupdict().items()}
                try:
                    handler(**kwargs)
                except MatrixAPIError as e:
                    self._error_response(e.status_code, str(e))
                except Exception as e:
                    logger.exception("Handler error")
                    self._error_response(500, str(e))
                return
        self._error_response(404, f"Not found: {method} {self.path}")

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    # ── Handlers ─────────────────────────────────────────────

    def handle_health(self) -> None:
        self._json_response({"status": "ok"})

    def handle_openapi(self) -> None:
        spec = _build_openapi_spec(
            self.server.server_address[0], self.server.server_address[1],
        )
        self._json_response(spec)

    def handle_whoami(self) -> None:
        result = self._run_async(self.client.whoami())
        self._json_response(result)

    def handle_list_rooms(self) -> None:
        room_ids = self._run_async(self.client.joined_rooms())
        results = []
        for rid in room_ids:
            name = self._run_async(self.client.get_room_name(rid))
            results.append({"room_id": rid, "name": name})
        self._json_response(results)

    def handle_create_room(self) -> None:
        body = self._read_json()
        invite = body.get("invite")
        if isinstance(invite, str):
            invite = [u.strip() for u in invite.split(",")]
        result = self._run_async(self.client.create_room(
            name=body.get("name"),
            topic=body.get("topic"),
            preset=body.get("preset", "private_chat"),
            invite=invite,
        ))
        self._json_response(result, 201)

    def handle_get_messages(self, room_id: str) -> None:
        from urllib.parse import urlparse, parse_qs

        qs = parse_qs(urlparse(self.path).query)
        limit = int(qs.get("limit", ["20"])[0])
        direction = qs.get("dir", ["b"])[0]
        result = self._run_async(self.client.get_messages(
            room_id, limit=limit, direction=direction,
        ))
        self._json_response(result)

    def handle_send_message(self, room_id: str) -> None:
        body = self._read_json()
        msg = body.get("body", "")
        if not msg:
            self._error_response(400, "Missing 'body' field")
            return
        result = self._run_async(self.client.send_message(
            room_id, msg,
            msgtype=body.get("msgtype", "m.text"),
            formatted_body=body.get("formatted_body"),
        ))
        self._json_response(result)

    def handle_send_reaction(self, room_id: str) -> None:
        body = self._read_json()
        event_id = body.get("event_id", "")
        emoji = body.get("emoji", "")
        if not event_id or not emoji:
            self._error_response(400, "Missing 'event_id' or 'emoji'")
            return
        result = self._run_async(self.client.send_reaction(room_id, event_id, emoji))
        self._json_response(result)

    def handle_redact(self, room_id: str) -> None:
        body = self._read_json()
        event_id = body.get("event_id", "")
        if not event_id:
            self._error_response(400, "Missing 'event_id'")
            return
        result = self._run_async(self.client.redact(
            room_id, event_id, reason=body.get("reason"),
        ))
        self._json_response(result)

    def handle_get_members(self, room_id: str) -> None:
        members = self._run_async(self.client.get_members(room_id))
        self._json_response(members)

    def handle_get_state(self, room_id: str, event_type: str) -> None:
        from urllib.parse import urlparse, parse_qs

        qs = parse_qs(urlparse(self.path).query)
        state_key = qs.get("state_key", [""])[0]
        result = self._run_async(self.client.get_state(room_id, event_type, state_key))
        self._json_response(result)

    def handle_set_state(self, room_id: str, event_type: str) -> None:
        from urllib.parse import urlparse, parse_qs

        qs = parse_qs(urlparse(self.path).query)
        state_key = qs.get("state_key", [""])[0]
        body = self._read_json()
        result = self._run_async(self.client.set_state(room_id, event_type, body, state_key))
        self._json_response(result)

    def handle_invite(self, room_id: str) -> None:
        body = self._read_json()
        user_id = body.get("user_id", "")
        if not user_id:
            self._error_response(400, "Missing 'user_id'")
            return
        self._run_async(self.client.invite(room_id, user_id))
        self._json_response({"status": "invited", "user_id": user_id})

    def handle_kick(self, room_id: str) -> None:
        body = self._read_json()
        user_id = body.get("user_id", "")
        if not user_id:
            self._error_response(400, "Missing 'user_id'")
            return
        self._run_async(self.client.kick(room_id, user_id, reason=body.get("reason")))
        self._json_response({"status": "kicked", "user_id": user_id})

    def handle_set_power_level(self, room_id: str) -> None:
        body = self._read_json()
        user_id = body.get("user_id", "")
        level = body.get("level")
        if not user_id or level is None:
            self._error_response(400, "Missing 'user_id' or 'level'")
            return
        self._run_async(self.client.set_user_power_level(room_id, user_id, int(level)))
        self._json_response({"status": "updated", "user_id": user_id, "level": level})

    def handle_get_display_name(self, user_id: str) -> None:
        name = self._run_async(self.client.get_display_name(user_id))
        self._json_response({"user_id": user_id, "displayname": name})


def run_rest_server(
    host: str = "127.0.0.1",
    port: int = 8989,
) -> None:
    """Start the REST/OpenAPI server.

    Args:
        host: Bind host.
        port: Bind port.
    """
    config = load_config()
    loop = asyncio.new_event_loop()
    client = loop.run_until_complete(_create_client(config))

    # Build a handler subclass with client/config/loop baked in.
    # BaseHTTPRequestHandler.__init__ dispatches the request immediately,
    # so attributes must be set before super().__init__ runs.
    handler_class = _make_handler_class(client, config, loop)
    server = HTTPServer((host, port), handler_class)
    logger.info("REST server listening on http://%s:%d", host, port)
    logger.info("OpenAPI spec at http://%s:%d/openapi.json", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(client.close())
        loop.close()
        server.server_close()


async def _create_client(config: Config) -> MatrixClient:
    client = MatrixClient(
        homeserver=config.homeserver,
        token=config.resolve_token(),
    )
    whoami = await client.whoami()
    logger.info("REST server connected as %s", whoami.get("user_id"))
    return client


def _make_handler_class(
    client: MatrixClient,
    config: Config,
    loop: asyncio.AbstractEventLoop,
) -> type[MatrixHandler]:
    """Create a MatrixHandler subclass with client/config/loop bound as class attrs.

    BaseHTTPRequestHandler.__init__ calls handle() → dispatch synchronously,
    so instance attributes set after __init__ are too late. Class-level attrs
    are available immediately.
    """

    class BoundHandler(MatrixHandler):
        pass

    BoundHandler.client = client  # type: ignore[attr-defined]
    BoundHandler.config = config  # type: ignore[attr-defined]
    BoundHandler._loop = loop  # type: ignore[attr-defined]
    return BoundHandler
