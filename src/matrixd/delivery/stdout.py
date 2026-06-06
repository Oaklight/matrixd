"""Stdout delivery — prints events to stdout.

Useful for piping into other processes or CLI usage.
"""

from __future__ import annotations

import sys

from ..core.policy import Event
from .base import DeliveryBackend


class StdoutDelivery(DeliveryBackend):
    def __init__(self, fmt: str = "json") -> None:
        self.fmt = fmt

    async def deliver(self, event: Event) -> None:
        line = self.serialize(event, self.fmt)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
