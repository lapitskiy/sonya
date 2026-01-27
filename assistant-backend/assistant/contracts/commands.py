from pydantic import BaseModel


class VoiceCommandIn(BaseModel):
    device_id: str = "default"
    text: str
    lat: float | None = None
    lon: float | None = None


class GeoPingIn(BaseModel):
    device_id: str = "default"
    lat: float
    lon: float

