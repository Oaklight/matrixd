# matrixd

[中文版](README_zh.md)

Matrix agent daemon — listener, tools, and hooks for AI agents.

Connects any AI agent platform to [Matrix](https://matrix.org) with policy-filtered event delivery. Works with OpenClaw, Claude Code, Talpa, and any platform that supports webhooks, stdio, or MCP.

## Features

- 🔄 **Listener** — `/sync` long-polling with automatic reconnection
- 🛡️ **Policy engine** — per-room filtering: lurk, mention-only, all, important
- 📡 **Pluggable delivery** — stdout, webhook, exec (pipe to any process)
- 🔧 **CLI tools** — `matrixd send`, `matrixd rooms`, `matrixd listen`
- 🔌 **MCP server** — bidirectional Matrix tools + notifications *(coming soon)*
- 🌐 **REST/OpenAPI server** — HTTP API for any language *(coming soon)*
- 📦 **Python library** — `import matrixd` for embedding in your own projects

## Installation

```bash
# Core (listener + CLI)
pip install matrixd

# With MCP server
pip install matrixd[mcp]

# With REST/OpenAPI server
pip install matrixd[api]

# Everything
pip install matrixd[full]
```

### From source

```bash
git clone https://github.com/Oaklight/matrixd.git
cd matrixd
pip install -e ".[dev]"
```

🇨🇳 **China mainland**: use jsdelivr for fast access to source files:
```
https://cdn.jsdelivr.net/gh/Oaklight/matrixd@master/README_en.md
```

## Quick start

```bash
# 1. Create config
cp matrixd.example.yaml matrixd.yaml
# Edit: set homeserver, token/token_file, room policies

# 2. Verify credentials
matrixd whoami

# 3. List rooms
matrixd rooms

# 4. Send a message
matrixd send '!roomid:server' 'Hello from matrixd'

# 5. Start listener
matrixd listen
```

## Configuration

```yaml
homeserver: https://matrix.example.com
token_file: ~/.openclaw/credentials/matrix/credentials.json

default_policy: lurk

rooms:
  "!dev:example.com":
    policy: all
  "!alerts:example.com":
    policy: mention-only

delivery:
  mode: webhook
  webhook_url: http://localhost:8080/events
```

See [matrixd.example.yaml](matrixd.example.yaml) for full reference.

### Policies

| Policy | Delivers |
|--------|----------|
| `lurk` | Nothing (monitor only) |
| `mention-only` | Bot is mentioned by name or user ID |
| `important` | Mentions + replies to bot's messages |
| `all` | Every message event |

### Delivery modes

| Mode | Target | Use case |
|------|--------|----------|
| `stdout` | Terminal / pipe | CLI, debugging, pipe to another process |
| `webhook` | HTTP endpoint | Any web service, Claude Code hooks |
| `exec` | Spawn command | Run a script per event, event JSON on stdin |

## Architecture

```
┌─────────────────────────────────────────────┐
│                  matrixd                     │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Client   │  │ Listener │  │  Policy   │  │
│  │ (httpx)   │  │ (/sync)  │→ │  engine   │──│──→ Delivery backends
│  └──────────┘  └──────────┘  └───────────┘  │    (stdout/webhook/exec)
│       ↑                                     │
│  ┌──────────────────────┐                   │
│  │  CLI / MCP / REST    │                   │
│  │  (tools interface)   │                   │
│  └──────────────────────┘                   │
└─────────────────────────────────────────────┘
```

## Relation to matrix-skill

[matrix-skill](https://github.com/Oaklight/matrix-skill) is a static SKILL.md teaching agents to use `curl+jq` for Matrix operations. It requires zero dependencies and works everywhere.

**matrixd** is the runtime companion:
- `matrix-skill` = knowledge (how to call the API)
- `matrixd` = runtime (persistent listener + typed Python client + delivery)

Use matrix-skill when you just need on-demand API calls. Use matrixd when you need persistent inbound listening, policy filtering, or a tool server.

## Compatibility

| Platform | How to connect |
|----------|---------------|
| **OpenClaw** | Webhook delivery to session API, or MCP server |
| **Claude Code** | MCP server (stdio transport) |
| **Talpa** | Webhook or Python library import |
| **Any agent** | Webhook, exec, or stdout pipe |

## License

[MIT](LICENSE)
