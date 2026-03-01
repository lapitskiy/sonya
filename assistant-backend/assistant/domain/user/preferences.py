"""User preferences (domain value objects)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationPreferences:
    """User notification preferences."""
    enabled: bool = True
    quiet_hours_start: int = 22  # 22:00
    quiet_hours_end: int = 8  # 08:00


@dataclass(frozen=True)
class UserPreferences:
    """User preferences aggregate."""
    device_id: str
    notifications: NotificationPreferences
