"""matrixd CLI entry point.

Commands:
    matrixd listen    — run the /sync listener with policy + delivery
    matrixd send      — send a message to a room
    matrixd rooms     — list joined rooms
    matrixd serve     — start MCP or REST server
    matrixd whoami    — verify credentials
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click

from .core.config import load_config


@click.group()
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Config file path (default: auto-detect).",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging.")
@click.pass_context
def main(ctx: click.Context, config_path: str | None, verbose: bool) -> None:
    """matrixd — Matrix agent daemon."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose


@main.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Verify Matrix credentials."""

    async def _run() -> None:
        cfg = load_config(ctx.obj["config_path"])
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            result = await client.whoami()
            click.echo(json.dumps(result, indent=2))

    asyncio.run(_run())


@main.command()
@click.argument("room_id")
@click.argument("message")
@click.option("--msgtype", default="m.text", help="Message type.")
@click.pass_context
def send(ctx: click.Context, room_id: str, message: str, msgtype: str) -> None:
    """Send a message to a room."""

    async def _run() -> None:
        cfg = load_config(ctx.obj["config_path"])
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            result = await client.send_message(room_id, message, msgtype=msgtype)
            click.echo(json.dumps(result, indent=2))

    asyncio.run(_run())


@main.command()
@click.pass_context
def rooms(ctx: click.Context) -> None:
    """List joined rooms with names."""

    async def _run() -> None:
        cfg = load_config(ctx.obj["config_path"])
        from .core.client import MatrixClient

        async with MatrixClient(cfg.homeserver, cfg.resolve_token()) as client:
            room_ids = await client.joined_rooms()
            for rid in room_ids:
                name = await client.get_room_name(rid)
                display = f"{rid} → {name}" if name else rid
                click.echo(display)

    asyncio.run(_run())


@main.command()
@click.option(
    "--delivery",
    "delivery_mode",
    type=click.Choice(["stdout", "webhook", "exec"]),
    default=None,
    help="Override delivery mode.",
)
@click.pass_context
def listen(ctx: click.Context, delivery_mode: str | None) -> None:
    """Run the /sync listener with policy filtering."""

    async def _run() -> None:
        cfg = load_config(ctx.obj["config_path"])
        if delivery_mode:
            cfg.delivery.mode = delivery_mode

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
            click.echo("Listening... (Ctrl+C to stop)", err=True)

            try:
                async for event in listener.listen():
                    await backend.deliver(event)
            except KeyboardInterrupt:
                pass
            finally:
                await backend.close()

    asyncio.run(_run())


@main.command()
@click.option(
    "--mode",
    type=click.Choice(["mcp", "rest"]),
    default="mcp",
    help="Server mode.",
)
@click.option("--host", default=None, help="Bind host.")
@click.option("--port", default=None, type=int, help="Bind port.")
@click.pass_context
def serve(ctx: click.Context, mode: str, host: str | None, port: int | None) -> None:
    """Start MCP or REST tool server."""
    cfg = load_config(ctx.obj["config_path"])
    if host:
        cfg.server.host = host
    if port:
        cfg.server.port = port

    if mode == "mcp":
        click.echo("MCP server mode — install matrixd[mcp] for full support.", err=True)
        click.echo("(MCP server implementation pending)", err=True)
        sys.exit(1)
    elif mode == "rest":
        click.echo(
            "REST server mode — install matrixd[api] for full support.", err=True
        )
        click.echo("(REST server implementation pending)", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
