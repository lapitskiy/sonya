from datetime import datetime

from sqlalchemy.orm import Session

from assistant.domain.reminder.entities import GeoTrigger, Reminder

from .models import EventModel, GeoTriggerModel, ReminderModel


class ReminderRepository:
    def __init__(self, db: Session):
        self._db = db

    def add(self, reminder: Reminder) -> int:
        row = ReminderModel(
            device_id=reminder.device_id,
            text=reminder.text,
            due_at=reminder.due_at,
            fired=False,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return int(row.id)

    def due_not_fired(self, now: datetime) -> list[ReminderModel]:
        return (
            self._db.query(ReminderModel)
            .filter(ReminderModel.fired.is_(False))
            .filter(ReminderModel.due_at <= now)
            .all()
        )


class GeoRepository:
    def __init__(self, db: Session):
        self._db = db

    def add(self, trig: GeoTrigger) -> int:
        row = GeoTriggerModel(
            device_id=trig.device_id,
            text=trig.text,
            lat=trig.lat,
            lon=trig.lon,
            radius_m=trig.radius_m,
            active=True,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return int(row.id)

    def active_for_device(self, device_id: str) -> list[GeoTriggerModel]:
        return (
            self._db.query(GeoTriggerModel)
            .filter(GeoTriggerModel.device_id == device_id)
            .filter(GeoTriggerModel.active.is_(True))
            .all()
        )


class EventRepository:
    def __init__(self, db: Session):
        self._db = db

    def add(self, device_id: str, type_: str, payload: dict) -> int:
        row = EventModel(device_id=device_id, type=type_, payload=payload, delivered=False)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return int(row.id)

    def poll_and_mark_delivered(self, device_id: str, limit: int) -> list[EventModel]:
        rows = (
            self._db.query(EventModel)
            .filter(EventModel.device_id == device_id)
            .filter(EventModel.delivered.is_(False))
            .order_by(EventModel.id.asc())
            .limit(limit)
            .all()
        )
        for r in rows:
            r.delivered = True
        if rows:
            self._db.commit()
        return rows

