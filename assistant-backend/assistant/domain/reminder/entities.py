from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reminder:
    device_id: str
    text: str
    due_at: datetime


@dataclass(frozen=True)
class GeoTrigger:
    device_id: str
    text: str
    lat: float
    lon: float
    radius_m: int

