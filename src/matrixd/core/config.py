"""Configuration loader.

Loads matrixd config from JSONC/JSON (via vendored zerodep jsonc module)
or YAML (optional dependency). Supports env var interpolation via ${VAR} syntax.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .._vendor.jsonc import loads as jsonc_loads
from .policy import RoomPolicy

DEFAULT_CONFIG_PATHS = [
    Path("matrixd.jsonc"),
    Path("matrixd.json"),
    Path("matrixd.yaml"),
    Path("matrixd.yml"),
    Path.home() / ".config" / "matrixd" / "config.jsonc",
    Path.home() / ".config" / "matrixd" / "config.json",
    Path.home() / ".config" / "matrixd" / "config.yaml",
    Path.home() / ".config" / "matrixd" / "config.yml",
]


def _load_file(path: Path) -> dict[str, Any]:
    """Load a config file, dispatching by extension."""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".jsonc", ".json"):
        return jsonc_loads(text)  # type: ignore[no-any-return]
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                f"YAML config file detected ({path}) but PyYAML is not installed. "
                "Install it with: pip install pyyaml\n"
                "Or use a JSONC config file instead (matrixd.jsonc)."
            ) from None
        return yaml.safe_load(text) or {}
    raise ValueError(f"Unsupported config format: {suffix} (use .jsonc, .json, or .yaml)")


@dataclass
class DeliveryConfig:
    """Delivery backend configuration."""

    mode: str = "stdout"  # stdout, webhook, exec
    webhook_url: str | None = None
    exec_cmd: list[str] | None = None
    format: str = "json"  # json, plain
    include_context: int = 0


@dataclass
class ServerConfig:
    """Server mode configuration."""

    host: str = "127.0.0.1"
    port: int = 8989
    # MCP-specific
    mcp_transport: str = "stdio"  # stdio, sse


@dataclass
class Config:
    """Top-level matrixd configuration."""

    homeserver: str = ""
    token: str = ""
    token_file: str | None = None

    # Listener
    room_policies: dict[str, RoomPolicy] = field(default_factory=dict)
    default_policy: RoomPolicy = RoomPolicy.LURK
    sync_timeout_ms: int = 30000
    context_messages: int = 0

    # Delivery
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)

    # Server
    server: ServerConfig = field(default_factory=ServerConfig)

    def resolve_token(self) -> str:
        """Resolve token from direct value or file."""
        if self.token:
            return self.token
        if self.token_file:
            path = Path(os.path.expanduser(self.token_file))
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("accessToken", data.get("access_token", ""))
            return path.read_text(encoding="utf-8").strip()
        raise ValueError("No token configured. Set 'token' or 'token_file'.")


def load_config(path: str | Path | None = None) -> Config:
    """Load config from JSON or YAML file.

    If path is None, searches default locations (JSON checked first).
    """
    if path:
        config_path = Path(path)
    else:
        config_path = None
        for default in DEFAULT_CONFIG_PATHS:
            if default.exists():
                config_path = default
                break
        if config_path is None:
            return Config()

    raw = _load_file(config_path)
    return _parse_config(raw)


def _parse_config(raw: dict[str, Any]) -> Config:
    """Parse raw dict into Config."""
    config = Config()

    config.homeserver = _env_str(raw.get("homeserver", ""))
    config.token = _env_str(raw.get("token", ""))
    config.token_file = raw.get("token_file")
    config.sync_timeout_ms = raw.get("sync_timeout_ms", 30000)
    config.context_messages = raw.get("context_messages", 0)

    # Default policy
    dp = raw.get("default_policy", "lurk")
    config.default_policy = RoomPolicy(dp)

    # Room policies
    rooms = raw.get("rooms", {})
    for room_id, room_cfg in rooms.items():
        if isinstance(room_cfg, str):
            config.room_policies[room_id] = RoomPolicy(room_cfg)
        elif isinstance(room_cfg, dict):
            policy_str = room_cfg.get("policy", "lurk")
            config.room_policies[room_id] = RoomPolicy(policy_str)

    # Delivery
    delivery_raw = raw.get("delivery", {})
    config.delivery = DeliveryConfig(
        mode=delivery_raw.get("mode", "stdout"),
        webhook_url=_env_str(delivery_raw.get("webhook_url", "")),
        exec_cmd=delivery_raw.get("exec_cmd"),
        format=delivery_raw.get("format", "json"),
        include_context=delivery_raw.get("include_context", 0),
    )

    # Server
    server_raw = raw.get("server", {})
    config.server = ServerConfig(
        host=server_raw.get("host", "127.0.0.1"),
        port=server_raw.get("port", 8989),
        mcp_transport=server_raw.get("mcp_transport", "stdio"),
    )

    return config


def _env_str(value: str) -> str:
    """Expand ${ENV_VAR} references in a string."""
    if not isinstance(value, str):
        return str(value) if value else ""
    return os.path.expandvars(value)
