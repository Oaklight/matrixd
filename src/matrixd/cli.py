"""matrixd CLI entry point.

Commands:
    matrixd listen    — run the /sync listener with policy + delivery
    matrixd send      — send a message to a room
    matrixd rooms     — list joined rooms
    matrixd serve     — start MCP or REST server
    matrixd whoami    — verify credentials
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from .core.config import load_config


def main(argv: list[str] | None = None) -> None:
    """matrixd — Matrix agent daemon."""
    parser = argparse.ArgumentParser(
        prog="matrixd",
        description="Matrix agent daemon — listener, tools, and hooks for AI agents.",
    )
    parser.add_argument(
        "-c", "--config", dest="config_path", default=None,
        help="Config file path (default: auto-detect).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging.",
    )

    sub = parser.add_subparsers(dest="command")

    # whoami
    sub.add_parser("whoami", help="Verify Matrix credentials.")

    # send
    send_p = sub.add_parser("send", help="Send a message to a room.")
    send_p.add_argument("room_id", help="Target room ID.")
    send_p.add_argument("message", help="Message body.")
    send_p.add_argument("--msgtype", default="m.text", help="Message type.")

    # rooms
    sub.add_parser("rooms", help="List joined rooms with names.")

    # listen
    listen_p = sub.add_parser("listen", help="Run the /sync listener with policy filtering.")
    listen_p.add_argument(
        "--delivery", dest="delivery_mode",
        choices=["stdout", "webhook", "exec"], default=None,
        help="Override delivery mode.",
    )

    # serve
    serve_p = sub.add_parser("serve", help="Start MCP or REST tool server.")
    serve_p.add_argument(
        "--mode", choices=["mcp", "rest"], default="mcp",
        help="Server mode.",
    )
    serve_p.add_argument("--host", default=None, help="Bind host.")
    serve_p.add_argument("--port", type=int, default=None, help="Bind port.")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    handler = {
        "whoami": _cmd_whoami,
        "send": _cmd_send,
        "rooms": _cmd_rooms,
        "listen": _cmd_listen,
        "serve": _cmd_serve,
    }[args.command]

    handler(args)


def _cmd_whoami(args: argparse.Namespace) -> None:
    async def _run() -> None:
        cfg = load_config(args.config_path)
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            result = await client.whoami()
            print(json.dumps(result, indent=2))

    asyncio.run(_run())


def _cmd_send(args: argparse.Namespace) -> None:
    async def _run() -> None:
        cfg = load_config(args.config_path)
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            result = await client.send_message(
                args.room_id, args.message, msgtype=args.msgtype,
            )
            print(json.dumps(result, indent=2))

    asyncio.run(_run())


def _cmd_rooms(args: argparse.Namespace) -> None:
    async def _run() -> None:
        cfg = load_config(args.config_path)
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            room_ids = await client.joined_rooms()
            for rid in room_ids:
                name = await client.get_room_name(rid)
                display = f"{rid} → {name}" if name else rid
                print(display)

    asyncio.run(_run())


def _cmd_listen(args: argparse.Namespace) -> None:
    async def _run() -> None:
        cfg = load_config(args.config_path)
        if args.delivery_mode:
            cfg.delivery.mode = args.delivery_mode

        from .core.client import MatrixClient
        from .core.listener import Listener, ListenerConfig
        from .delivery.base import create_backend

        listener_cfg = ListenerConfig(
            room_policies=cfg.room_policies,
            default_policy=cfg.default_policy,
            sync_timeout_ms=cfg.sync_timeout_ms,
            context_messages=cfg.context_messages,
        )

        backend = create_backend(
            cfg.delivery.mode,
            webhook_url=cfg.delivery.webhook_url,
            exec_cmd=cfg.delivery.exec_cmd,
            format=cfg.delivery.format,
        )

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            listener = Listener(client, listener_cfg)
            await listener.do_initial_sync()
            print("Listening... (Ctrl+C to stop)", file=sys.stderr)

            try:
                async for event in listener.listen():
                    await backend.deliver(event)
            except KeyboardInterrupt:
                pass
            finally:
                await backend.close()

    asyncio.run(_run())


def _cmd_serve(args: argparse.Namespace) -> None:
    cfg = load_config(args.config_path)
    if args.host:
        cfg.server.host = args.host
    if args.port:
        cfg.server.port = args.port

    if args.mode == "mcp":
        print("MCP server mode — install matrixd[mcp] for full support.", file=sys.stderr)
        print("(MCP server implementation pending)", file=sys.stderr)
        sys.exit(1)
    elif args.mode == "rest":
        print("REST server mode — install matrixd[api] for full support.", file=sys.stderr)
        print("(REST server implementation pending)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
