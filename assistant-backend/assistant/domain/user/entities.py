"""User domain entities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceId:
    """Device identifier."""
    value: str


@dataclass(frozen=True)
class User:
    """User entity."""
    device_id: DeviceId
