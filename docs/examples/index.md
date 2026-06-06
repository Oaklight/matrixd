# Examples

## Send a Message

```bash
matrixd send '!room:example.com' 'Hello from matrixd'
```

## List Joined Rooms

```bash
matrixd rooms
```

Output:

```
!abc123:example.com → General
!dev:example.com → dev-team
!alerts:example.com → Alerts
```

## Pipe Events to jq

```bash
matrixd listen --delivery stdout | jq '.body'
```

## Webhook to a Local Server

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

## Process Events with a Script

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

`handle_event.py`:

```python
import json
import sys

event = json.load(sys.stdin)
print(f"Got message from {event['sender']}: {event['body']}")

# Reply logic, forward to another service, etc.
```

## Python Library Usage

### Send a Message

```python
import asyncio
from matrixd.core.client import MatrixClient

async def main():
    async with MatrixClient("https://matrix.example.com", "syt_...") as client:
        result = await client.send_message("!room:example.com", "Hello!")
        print(result)

asyncio.run(main())
```

### Monitor a Room

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

### Create a Room and Invite Users

```python
import asyncio
from matrixd.core.client import MatrixClient

async def main():
    async with MatrixClient("https://matrix.example.com", "syt_...") as client:
        room = await client.create_room(
            name="project-channel",
            topic="Discuss the project",
            invite=["@alice:example.com", "@bob:example.com"],
        )
        print(f"Created room: {room['room_id']}")

asyncio.run(main())
```
