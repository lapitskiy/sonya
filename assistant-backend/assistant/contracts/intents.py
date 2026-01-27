from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class GeoPoint(BaseModel):
    lat: float
    lon: float


class ReminderIntent(BaseModel):
    type: Literal["time"]
    due_at: datetime


class GeoIntent(BaseModel):
    type: Literal["geo"]
    location: GeoPoint
    radius_m: int = 150


class UnknownIntent(BaseModel):
    type: Literal["unknown"]


Intent = ReminderIntent | GeoIntent | UnknownIntent

