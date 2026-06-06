# Configuration

matrixd uses **JSONC** (JSON with Comments) for configuration. Plain JSON files also work.

## Config File Location

matrixd searches for config in this order:

1. `matrixd.jsonc` (current directory)
2. `matrixd.json` (current directory)
3. `~/.config/matrixd/config.jsonc`
4. `~/.config/matrixd/config.json`

Or specify explicitly:

```bash
matrixd -c /path/to/config.jsonc whoami
```

## Full Example

```jsonc
{
  // Matrix homeserver URL
  "homeserver": "https://matrix.example.com",

  // Authentication: direct token or file path
  // "token": "syt_...",
  "token_file": "~/.openclaw/credentials/matrix/credentials.json",

  // Default policy for rooms not listed below
  // Options: lurk | mention-only | all | important
  "default_policy": "lurk",

  // Per-room policy overrides
  "rooms": {
    "!abc123:example.com": { "policy": "all" },
    "!dev-room:example.com": { "policy": "mention-only" },
    "!alerts:example.com": { "policy": "important" },
  },

  // /sync long-poll timeout (ms)
  "sync_timeout_ms": 30000,

  // Delivery backend
  "delivery": {
    "mode": "stdout",    // stdout | webhook | exec
    "format": "json",    // json | plain

    // Webhook mode:
    // "mode": "webhook",
    // "webhook_url": "http://localhost:8080/matrix-events",

    // Exec mode — event JSON piped to stdin:
    // "mode": "exec",
    // "exec_cmd": ["python", "handle_event.py"],
  },

  // Server settings (for `matrixd serve`)
  "server": {
    "host": "127.0.0.1",
    "port": 8989,
    "mcp_transport": "stdio", // stdio | sse
  },
}
```

## Authentication

### Direct Token

```jsonc
{
  "token": "syt_your_access_token_here"
}
```

### Token File

Point to a file containing the token. Supports JSON files (reads `accessToken` or `access_token` field) and plain text files.

```jsonc
{
  "token_file": "~/.openclaw/credentials/matrix/credentials.json"
}
```

### Environment Variables

Use `${VAR}` syntax for env var interpolation:

```jsonc
{
  "token": "${MATRIX_TOKEN}",
  "homeserver": "${MATRIX_HOMESERVER}"
}
```

## Room Policies

| Policy | Events Delivered |
|--------|-----------------|
| `lurk` | None (monitor only) |
| `mention-only` | Bot is mentioned by name or user ID |
| `important` | Mentions + replies to bot's messages |
| `all` | Every message event |

## Delivery Modes

### stdout

Prints events to stdout as JSON or plain text. Useful for piping to other processes.

```jsonc
{
  "delivery": {
    "mode": "stdout",
    "format": "json"  // or "plain"
  }
}
```

### webhook

POSTs event JSON to an HTTP endpoint.

```jsonc
{
  "delivery": {
    "mode": "webhook",
    "webhook_url": "http://localhost:8080/matrix-events"
  }
}
```

### exec

Spawns a command per event, piping event JSON to stdin.

```jsonc
{
  "delivery": {
    "mode": "exec",
    "exec_cmd": ["python", "handle_event.py"]
  }
}
```
