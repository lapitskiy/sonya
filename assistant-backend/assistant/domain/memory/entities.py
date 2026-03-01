"""Memory domain entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """Type of memory."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"


@dataclass(frozen=True)
class MemoryId:
    """Memory identifier."""
    value: int


@dataclass(frozen=True)
class Memory:
    """Memory entity (episodic or semantic)."""
    id: MemoryId
    device_id: str
    type: MemoryType
    content: str
    summary: str | None
    created_at: datetime
