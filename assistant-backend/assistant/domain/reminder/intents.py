"""Reminder intents (domain-level)."""

from dataclasses import dataclass
from datetime import datetime

from .value_objects import GeoTrigger, TimeTrigger


@dataclass(frozen=True)
class CreateReminderIntent:
    """Intent to create a reminder."""
    text: str
    trigger: TimeTrigger | GeoTrigger
