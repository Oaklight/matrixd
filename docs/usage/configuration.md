# 配置

matrixd 使用 **JSONC**（带注释的 JSON）作为配置格式。普通 JSON 文件也兼容。

## 配置文件搜索路径

matrixd 按以下顺序查找配置：

1. `matrixd.jsonc`（当前目录）
2. `matrixd.json`（当前目录）
3. `~/.config/matrixd/config.jsonc`
4. `~/.config/matrixd/config.json`

或手动指定：

```bash
matrixd -c /path/to/config.jsonc whoami
```

## 完整示例

```jsonc
{
  // Matrix homeserver 地址
  "homeserver": "https://matrix.example.com",

  // 认证：直接写 token 或指定文件路径
  // "token": "***",
  "token_file": "~/.openclaw/credentials/matrix/credentials.json",

  // 未配置的房间使用的默认策略
  // 选项：lurk | mention-only | all | important
  "default_policy": "lurk",

  // 按房间覆盖策略
  "rooms": {
    "!abc123:example.com": { "policy": "all" },
    "!dev-room:example.com": { "policy": "mention-only" },
    "!alerts:example.com": { "policy": "important" },
  },

  // /sync 长轮询超时（毫秒）
  "sync_timeout_ms": 30000,

  // 分发后端
  "delivery": {
    "mode": "stdout",    // stdout | webhook | exec
    "format": "json",    // json | plain

    // Webhook 模式：
    // "mode": "webhook",
    // "webhook_url": "http://localhost:8080/matrix-events",

    // Exec 模式 — 事件 JSON 通过 stdin 传入：
    // "mode": "exec",
    // "exec_cmd": ["python", "handle_event.py"],
  },

  // 服务器配置（用于 `matrixd serve`）
  "server": {
    "host": "127.0.0.1",
    "port": 8989,
    "mcp_transport": "stdio", // stdio | sse
  },
}
```

## 认证方式

### 直接 Token

```jsonc
{
  "token": "syt_yo…here"
}
```

### Token 文件

指向包含 token 的文件。支持 JSON 文件（读取 `accessToken` 或 `access_token` 字段）和纯文本文件。

```jsonc
{
  "token_file": "~/.openclaw/credentials/matrix/credentials.json"
}
```

### 环境变量

使用 `${VAR}` 语法引用环境变量：

```jsonc
{
  "token": "***",
  "homeserver": "${MATRIX_HOMESERVER}"
}
```

## 房间策略

| 策略 | 分发的事件 |
|------|-----------|
| `lurk` | 不分发（仅监控） |
| `mention-only` | 通过名称或用户 ID 提及了 bot |
| `important` | 提及 + 回复 bot 消息 |
| `all` | 所有消息事件 |

## 分发模式

### stdout

将事件以 JSON 或纯文本形式输出到 stdout。适合管道到其他进程。

```jsonc
{
  "delivery": {
    "mode": "stdout",
    "format": "json"  // 或 "plain"
  }
}
```

### webhook

将事件 JSON POST 到 HTTP 端点。

```jsonc
{
  "delivery": {
    "mode": "webhook",
    "webhook_url": "http://localhost:8080/matrix-events"
  }
}
```

### exec

每个事件启动一个命令，事件 JSON 通过 stdin 传入。

```jsonc
{
  "delivery": {
    "mode": "exec",
    "exec_cmd": ["python", "handle_event.py"]
  }
}
```
