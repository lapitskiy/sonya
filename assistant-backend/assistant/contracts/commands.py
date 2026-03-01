from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class VoiceCommandIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    device_id: str = Field(default="default", alias="deviceId")
    text: str
    lat: float | None = None
    lon: float | None = None
    device_time: datetime | None = Field(default=None, alias="deviceTime")


class GeoPingIn(BaseModel):
    device_id: str = "default"
    lat: float
    lon: float

