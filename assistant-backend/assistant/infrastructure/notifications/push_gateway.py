"""Push notification gateway (infrastructure)."""

from __future__ import annotations

from ..db.repositories import EventRepository


class PushGateway:
    """Gateway for sending push notifications.

    MVP implementation: store as event in DB (UI can poll /events).
    """

    def __init__(self, events: EventRepository):
        self._events = events

    def send(self, device_id: str, title: str, body: str) -> None:
        self._events.add(
            device_id=device_id,
            type_="push.reminder",
            payload={"title": title, "body": body},
        )
