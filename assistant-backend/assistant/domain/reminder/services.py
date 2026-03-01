"""Reminder domain services (pure logic, no IO)."""

from datetime import datetime, timezone

from .entities import Reminder
from .rules import ensure_future, ensure_radius
from .value_objects import GeoTrigger, ReminderStatus, TimeTrigger


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_trigger(trigger: TimeTrigger | GeoTrigger, now: datetime) -> None:
    """Validate trigger according to domain rules."""
    if isinstance(trigger, TimeTrigger):
        ensure_future(_as_utc_aware(trigger.due_at), _as_utc_aware(now))
    elif isinstance(trigger, GeoTrigger):
        ensure_radius(trigger.radius_m)


def should_fire(reminder: Reminder, now: datetime) -> bool:
    """Check if reminder should fire (domain logic only)."""
    if reminder.status != ReminderStatus.PENDING:
        return False
    
    if isinstance(reminder.trigger, TimeTrigger):
        return _as_utc_aware(reminder.trigger.due_at) <= _as_utc_aware(now)
    
    # Geo triggers are evaluated externally
    return False
