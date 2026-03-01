"""Process geo ping: detect enter/exit transitions for saved places and enqueue reminders."""

from datetime import datetime, timedelta

from ..infrastructure.db.repositories import (
    DeviceLocationRepository,
    PendingActionRepository,
    PlaceReminderRepository,
    PlaceRepository,
)
from ..infrastructure.geo.geofence import GeofenceService


class ProcessGeoPing:
    """
    Use case:
      - compare previous and current device location
      - detect transitions for each place (enter/exit)
      - enqueue matching place reminders into pending_actions
    """

    # Simple anti-bounce / dedupe window for the same reminder.
    _DEDUP_WINDOW = timedelta(minutes=5)

    def __init__(
        self,
        *,
        places: PlaceRepository,
        place_reminders: PlaceReminderRepository,
        device_locations: DeviceLocationRepository,
        pending_actions: PendingActionRepository,
        geofence: GeofenceService,
    ):
        self.places = places
        self.place_reminders = place_reminders
        self.device_locations = device_locations
        self.pending_actions = pending_actions
        self.geofence = geofence

    def execute(self, *, device_id: str, lat: float, lon: float, now: datetime) -> list[dict]:
        prev = self.device_locations.get(device_id=device_id)
        places = self.places.list_by_device(device_id=device_id)

        fired: list[dict] = []
        for p in places:
            is_inside = self.geofence.is_inside(lat, lon, p.lat, p.lon, p.radius_m)
            if prev is None:
                # First ping: initialize state without firing.
                continue
            was_inside = self.geofence.is_inside(prev.lat, prev.lon, p.lat, p.lon, p.radius_m)

            event: str | None = None
            if (not was_inside) and is_inside:
                event = "enter"
                self.places.touch_last_seen(place_id=int(p.id), now=now)
            elif was_inside and (not is_inside):
                event = "exit"

            if not event:
                continue

            rows = self.place_reminders.list_active_by_place(place_id=int(p.id), event=event)
            for r in rows:
                if r.last_fired_at is not None and (now - r.last_fired_at) < self._DEDUP_WINDOW:
                    continue
                payload = {
                    "type": "geo-alarm",
                    "place": getattr(p, "title", None),
                    "event": event,
                    "text": getattr(r, "text", ""),
                    "place_id": int(p.id),
                    "place_reminder_id": int(r.id),
                }
                # dedupe_key: stable per (reminder,event,minute)
                dedupe_key = f"geo-alarm:{int(r.id)}:{event}:{int(now.timestamp())//60}"
                self.pending_actions.create(
                    device_id=device_id,
                    action_type="geo-alarm",
                    payload=payload,
                    status="pending",
                    dedupe_key=dedupe_key,
                    request_id=None,
                    ttl_sec=3600,
                )
                self.place_reminders.mark_fired(reminder_id=int(r.id), now=now)
                fired.append(payload)

        # Update last known location at the end (so transitions compare against previous ping).
        self.device_locations.upsert(device_id=device_id, lat=lat, lon=lon, ts=now)
        return fired

