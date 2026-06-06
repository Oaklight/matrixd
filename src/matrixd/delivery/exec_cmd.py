"""Exec delivery — spawn a command with event data as stdin."""

from __future__ import annotations

import asyncio
import logging

from ..core.policy import Event
from .base import DeliveryBackend

logger = logging.getLogger(__name__)


class ExecDelivery(DeliveryBackend):
    def __init__(self, cmd: list[str], fmt: str = "json") -> None:
        self.cmd = cmd
        self.fmt = fmt

    async def deliver(self, event: Event) -> None:
        data = self.serialize(event, self.fmt)
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(data.encode())
            if proc.returncode != 0:
                logger.warning(
                    "Exec %s exited %d: %s",
                    self.cmd,
                    proc.returncode,
                    stderr.decode()[:200],
                )
        except Exception:
            logger.exception("Exec delivery failed: %s", self.cmd)
