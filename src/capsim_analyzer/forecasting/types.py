from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


class ForecastStatus(str, Enum):
    AVAILABLE = "available"
    INSUFFICIENT_HISTORY = "insufficient_history"
    MISSING_INPUT = "missing_input"
    ZERO_DENOMINATOR = "zero_denominator"
    UNSUPPORTED = "unsupported"


T = TypeVar("T")


@dataclass(frozen=True)
class ForecastValue(Generic[T]):
    value: T | None
    status: ForecastStatus
    method: str
    source_rounds: tuple[int, ...]
    required_history: int
    available_history: int
    assumptions: tuple[str, ...] = ()
