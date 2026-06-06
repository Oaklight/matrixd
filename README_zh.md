# matrixd

[English](README_en.md)

Matrix agent daemon — 为 AI agent 提供监听、工具和 hook 的 Matrix 守护进程。

将任意 AI agent 平台连接到 [Matrix](https://matrix.org)，支持策略过滤的事件投递。兼容 OpenClaw、Claude Code、Talpa，以及任何支持 webhook、stdio 或 MCP 的平台。

## 功能

- 🔄 **监听器** — `/sync` 长轮询，自动重连
- 🛡️ **策略引擎** — 按房间过滤：静默、仅提及、全部、重要
- 📡 **可插拔投递** — stdout、webhook、exec（管道到任意进程）
- 🔧 **CLI 工具** — `matrixd send`、`matrixd rooms`、`matrixd listen`
- 🔌 **MCP 服务器** — 双向 Matrix 工具 + 通知 *（即将推出）*
- 🌐 **REST/OpenAPI 服务器** — 任何语言可调用的 HTTP API *（即将推出）*
- 📦 **Python 库** — `import matrixd` 嵌入你自己的项目

## 安装

```bash
# 核心（监听器 + CLI）
pip install matrixd

# 含 MCP 服务器
pip install matrixd[mcp]

# 含 REST/OpenAPI 服务器
pip install matrixd[api]

# 全家桶
pip install matrixd[full]
```

### 从源码安装

```bash
git clone https://github.com/Oaklight/matrixd.git
cd matrixd
pip install -e ".[dev]"
```

🇨🇳 **中国大陆**：通过 jsdelivr 加速访问源文件：
```
https://cdn.jsdelivr.net/gh/Oaklight/matrixd@master/README_zh.md
```

## 快速上手

```bash
# 1. 创建配置
cp matrixd.example.yaml matrixd.yaml
# 编辑：设置 homeserver、token/token_file、房间策略

# 2. 验证凭证
matrixd whoami

# 3. 列出房间
matrixd rooms

# 4. 发送消息
matrixd send '!roomid:server' '来自 matrixd 的消息'

# 5. 启动监听
matrixd listen
```

## 配置

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

完整参考见 [matrixd.example.yaml](matrixd.example.yaml)。

### 策略

| 策略 | 投递范围 |
|------|---------|
| `lurk` | 不投递（仅监控） |
| `mention-only` | 被提及时（名称或用户 ID） |
| `important` | 提及 + 回复 bot 消息 |
| `all` | 所有消息事件 |

### 投递模式

| 模式 | 目标 | 场景 |
|------|------|------|
| `stdout` | 终端 / 管道 | CLI 调试、管道到其他进程 |
| `webhook` | HTTP 端点 | 任意 web 服务、Claude Code hook |
| `exec` | 执行命令 | 每个事件运行脚本，JSON 通过 stdin 传入 |

## 架构

```
┌─────────────────────────────────────────────┐
│                  matrixd                     │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Client   │  │ Listener │  │  Policy   │  │
│  │ (httpx)   │  │ (/sync)  │→ │  engine   │──│──→ 投递后端
│  └──────────┘  └──────────┘  └───────────┘  │  (stdout/webhook/exec)
│       ↑                                     │
│  ┌──────────────────────┐                   │
│  │  CLI / MCP / REST    │                   │
│  │  (工具接口)           │                   │
│  └──────────────────────┘                   │
└─────────────────────────────────────────────┘
```

## 与 matrix-skill 的关系

[matrix-skill](https://github.com/Oaklight/matrix-skill) 是静态 SKILL.md，教 agent 用 `curl+jq` 操作 Matrix API。零依赖，任何环境都能用。

**matrixd** 是运行时搭档：
- `matrix-skill` = 知识（怎么调 API）
- `matrixd` = 运行时（持久监听 + 类型化 Python 客户端 + 投递）

只需要按需 API 调用时用 matrix-skill。需要持久化入站监听、策略过滤或工具服务器时用 matrixd。

## 兼容性

| 平台 | 接入方式 |
|------|---------|
| **OpenClaw** | Webhook 投递到 session API，或 MCP 服务器 |
| **Claude Code** | MCP 服务器（stdio 传输） |
| **Talpa** | Webhook 或 Python 库导入 |
| **任意 agent** | Webhook、exec 或 stdout 管道 |

## 许可证

[MIT](LICENSE)
