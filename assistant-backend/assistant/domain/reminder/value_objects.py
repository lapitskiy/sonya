"""Value objects for reminder domain."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReminderStatus(str, Enum):
    """Reminder status."""
    PENDING = "pending"
    FIRED = "fired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ReminderId:
    """Reminder identifier."""
    value: int


@dataclass(frozen=True)
class Trigger:
    """Base trigger value object."""
    pass


@dataclass(frozen=True)
class TimeTrigger(Trigger):
    """Time-based trigger."""
    due_at: datetime


@dataclass(frozen=True)
class GeoTrigger(Trigger):
    """Geo-based trigger."""
    lat: float
    lon: float
    radius_m: int
