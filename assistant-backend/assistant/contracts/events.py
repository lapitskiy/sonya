from typing import Literal

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    type: Literal["reminder", "geo"]
    payload: dict

