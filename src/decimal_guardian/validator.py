from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ValidatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionResult:
    status: str
    tx_hash: str | None


class ValidatorProvider(Protocol):
    def paused(self) -> bool: ...

    def set_paused(self, paused: bool) -> ActionResult: ...
