"""Reminder domain entities."""

from dataclasses import dataclass

from .value_objects import ReminderId, ReminderStatus, Trigger


@dataclass(frozen=True)
class Reminder:
    """Reminder entity (pure domain, no IO)."""
    id: ReminderId
    device_id: str
    text: str
    trigger: Trigger
    status: ReminderStatus

