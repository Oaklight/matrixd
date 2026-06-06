# 示例

## 发送消息

```bash
matrixd send '!room:example.com' '来自 matrixd 的消息'
```

## 列出已加入的房间

```bash
matrixd rooms
```

输出：

```
!abc123:example.com → 综合讨论
!dev:example.com → dev-team
!alerts:example.com → 告警
```

## 将事件管道到 jq

```bash
matrixd listen --delivery stdout | jq '.body'
```

## Webhook 到本地服务器

```jsonc
// matrixd.jsonc
{
  "homeserver": "https://matrix.example.com",
  "token_file": "~/.config/matrixd/token.txt",
  "default_policy": "all",
  "delivery": {
    "mode": "webhook",
    "webhook_url": "http://localhost:8080/matrix-events"
  }
}
```

```bash
matrixd listen
```

## 用脚本处理事件

```jsonc
// matrixd.jsonc
{
  "homeserver": "https://matrix.example.com",
  "token_file": "~/.config/matrixd/token.txt",
  "default_policy": "mention-only",
  "delivery": {
    "mode": "exec",
    "exec_cmd": ["python", "handle_event.py"]
  }
}
```

`handle_event.py`：

```python
import json
import sys

event = json.load(sys.stdin)
print(f"收到来自 {event['sender']} 的消息: {event['body']}")

# 回复逻辑、转发到其他服务……
```

## Python 库用法

### 发送消息

```python
import asyncio
from matrixd.core.client import MatrixClient

async def main():
    async with MatrixClient("https://matrix.example.com", "syt_...") as client:
        result = await client.send_message("!room:example.com", "你好！")
        print(result)

asyncio.run(main())
```

### 监控房间

```python
import asyncio
from matrixd.core.client import MatrixClient
from matrixd.core.listener import Listener, ListenerConfig
from matrixd.core.policy import RoomPolicy

async def main():
    async with MatrixClient("https://matrix.example.com", "syt_...") as client:
        config = ListenerConfig(default_policy=RoomPolicy.ALL)
        listener = Listener(client, config)
        await listener.do_initial_sync()

        async for event in listener.listen():
            print(f"[{event.room_id}] {event.sender}: {event.body}")

asyncio.run(main())
```

### 创建房间并邀请用户

```python
import asyncio
from matrixd.core.client import MatrixClient

async def main():
    async with MatrixClient("https://matrix.example.com", "syt_...") as client:
        room = await client.create_room(
            name="项目频道",
            topic="讨论项目进展",
            invite=["@alice:example.com", "@bob:example.com"],
        )
        print(f"创建房间: {room['room_id']}")

asyncio.run(main())
```
