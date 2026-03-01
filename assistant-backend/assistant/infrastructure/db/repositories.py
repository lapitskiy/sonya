"""Repository implementations (infrastructure layer)."""

from datetime import date, datetime, timedelta, timezone
import math

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.reminder import Reminder, ReminderId, ReminderStatus
from ...domain.reminder.value_objects import GeoTrigger, TimeTrigger

from .models import (
    DeviceLastLocationModel,
    EventModel,
    GeoTriggerModel,
    PendingActionModel,
    PlaceModel,
    PlaceReminderModel,
    ReminderModel,
    TaskCategoryModel,
    TaskModel,
    VariableModel,
)


class ReminderRepository:
    """Repository for reminders."""
    
    def __init__(self, db: Session):
        self._db = db

    def save(self, reminder: Reminder) -> Reminder:
        """Save reminder and return with ID."""
        if isinstance(reminder.trigger, TimeTrigger):
            due_at = reminder.trigger.due_at
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)
            row = ReminderModel(
                device_id=reminder.device_id,
                text=reminder.text,
                due_at=due_at,
                fired=(reminder.status == ReminderStatus.FIRED),
            )
        elif isinstance(reminder.trigger, GeoTrigger):
            # For geo triggers, also save to GeoTriggerModel
            geo_row = GeoTriggerModel(
                device_id=reminder.device_id,
                text=reminder.text,
                lat=reminder.trigger.lat,
                lon=reminder.trigger.lon,
                radius_m=reminder.trigger.radius_m,
                active=(reminder.status == ReminderStatus.PENDING),
            )
            self._db.add(geo_row)
            self._db.flush()
            
            # Also create ReminderModel entry for consistency
            row = ReminderModel(
                device_id=reminder.device_id,
                text=reminder.text,
                due_at=datetime.max.replace(tzinfo=timezone.utc),  # Placeholder for geo triggers
                fired=False,
            )
        else:
            raise ValueError(f"Unsupported trigger type: {type(reminder.trigger)}")
        
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        
        # Return domain entity with ID
        return Reminder(
            id=ReminderId(value=row.id),
            device_id=reminder.device_id,
            text=reminder.text,
            trigger=reminder.trigger,
            status=reminder.status,
        )

    def find_due_not_fired(self, now: datetime) -> list[Reminder]:
        """Find reminders that are due and not fired."""
        rows = (
            self._db.query(ReminderModel)
            .filter(ReminderModel.fired.is_(False))
            .filter(ReminderModel.due_at <= now)
            .all()
        )
        
        # Convert to domain entities
        reminders = []
        for row in rows:
            trigger = TimeTrigger(due_at=row.due_at)
            status = ReminderStatus.FIRED if row.fired else ReminderStatus.PENDING
            reminders.append(Reminder(
                id=ReminderId(value=row.id),
                device_id=row.device_id,
                text=row.text,
                trigger=trigger,
                status=status,
            ))
        return reminders

    def mark_fired(self, *, reminder_id: int) -> None:
        row = self._db.query(ReminderModel).filter(ReminderModel.id == int(reminder_id)).one_or_none()
        if row is None:
            return
        row.fired = True
        self._db.commit()

    def find_active_geo_by_device(self, device_id: str) -> list[Reminder]:
        """Find active geo reminders for device."""
        rows = (
            self._db.query(GeoTriggerModel)
            .filter(GeoTriggerModel.device_id == device_id)
            .filter(GeoTriggerModel.active.is_(True))
            .all()
        )
        
        reminders = []
        for row in rows:
            trigger = GeoTrigger(
                lat=row.lat,
                lon=row.lon,
                radius_m=row.radius_m,
            )
            reminders.append(Reminder(
                id=ReminderId(value=0),  # Geo triggers don't have reminder ID yet
                device_id=row.device_id,
                text=row.text,
                trigger=trigger,
                status=ReminderStatus.PENDING,
            ))
        return reminders




class EventRepository:
    def __init__(self, db: Session):
        self._db = db

    def add(self, device_id: str, type_: str, payload: dict) -> int:
        row = EventModel(device_id=device_id, type=type_, payload=payload, delivered=False)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return int(row.id)

    def list_events(
        self,
        *,
        type_: str | None = None,
        device_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventModel]:
        q = self._db.query(EventModel)
        if type_:
            q = q.filter(EventModel.type == type_)
        if device_id:
            q = q.filter(EventModel.device_id == device_id)
        return (
            q.order_by(EventModel.id.desc())
            .offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

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


class VariableRepository:
    def __init__(self, db: Session):
        self._db = db

    def list(self, *, limit: int = 500, offset: int = 0) -> list[VariableModel]:
        return (
            self._db.query(VariableModel)
            .order_by(VariableModel.id.desc())
            .offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

    def create(
        self,
        *,
        scope: str,
        title: str,
        name: str,
        value_type: str,
        value: str,
    ) -> VariableModel:
        row = VariableModel(scope=scope, title=title, name=name, value_type=value_type, value=value)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def update(
        self,
        *,
        variable_id: int,
        scope: str,
        title: str,
        name: str,
        value_type: str,
        value: str,
    ) -> VariableModel | None:
        row = self._db.query(VariableModel).filter(VariableModel.id == int(variable_id)).one_or_none()
        if row is None:
            return None
        row.scope = scope
        row.title = title
        row.name = name
        row.value_type = value_type
        row.value = value
        self._db.commit()
        self._db.refresh(row)
        return row

    def get(self, *, scope: str, name: str) -> VariableModel | None:
        return (
            self._db.query(VariableModel)
            .filter(VariableModel.scope == scope)
            .filter(VariableModel.name == name)
            .one_or_none()
        )

    def get_value(self, *, scope: str, name: str, default: str | None = None) -> str | None:
        row = self.get(scope=scope, name=name)
        if row is None:
            return default
        return row.value


class PendingActionRepository:
    def __init__(self, db: Session):
        self._db = db

    def expire_due(self) -> int:
        """Mark expired pending actions based on expires_at."""
        now = datetime.utcnow()
        # IMPORTANT: keep this as a single SQL UPDATE to avoid loading rows into ORM,
        # which can be very slow and may hold locks longer than needed on large tables.
        updated = (
            self._db.query(PendingActionModel)
            .filter(PendingActionModel.status == "pending")
            .filter(PendingActionModel.expires_at.is_not(None))
            .filter(PendingActionModel.expires_at <= now)
            .update({PendingActionModel.status: "expired"}, synchronize_session=False)
        )
        if not updated:
            return 0
        self._db.commit()
        return int(updated)

    def create(
        self,
        *,
        device_id: str,
        action_type: str,
        payload: dict,
        status: str = "pending",
        dedupe_key: str | None = None,
        request_id: str | None = None,
        ttl_sec: int = 3600,
    ) -> PendingActionModel:
        if dedupe_key:
            existing = (
                self._db.query(PendingActionModel)
                .filter(PendingActionModel.device_id == device_id)
                .filter(PendingActionModel.dedupe_key == dedupe_key)
                .one_or_none()
            )
            if existing is not None:
                return existing

        now = datetime.utcnow()
        expires_at = None
        if status == "pending" and ttl_sec and int(ttl_sec) > 0:
            expires_at = now + timedelta(seconds=int(ttl_sec))

        row = PendingActionModel(
            device_id=device_id,
            request_id=request_id,
            action_type=action_type,
            payload=payload,
            status=status,
            dedupe_key=dedupe_key,
            ack=None,
            pulled_at=None,
            expires_at=expires_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_pending(self, *, device_id: str, limit: int = 100, offset: int = 0) -> list[PendingActionModel]:
        # TTL enforcement for read path: do not mutate DB on GET.
        now = datetime.utcnow()
        return (
            self._db.query(PendingActionModel)
            .filter(PendingActionModel.device_id == device_id)
            .filter(PendingActionModel.status == "pending")
            .filter(or_(PendingActionModel.expires_at.is_(None), PendingActionModel.expires_at > now))
            .order_by(PendingActionModel.id.asc())
            .offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

    def mark_pulled(self, *, action_ids: list[int]) -> None:
        if not action_ids:
            return
        now = datetime.utcnow()
        rows = self._db.query(PendingActionModel).filter(PendingActionModel.id.in_(action_ids)).all()
        changed = False
        for r in rows:
            if r.pulled_at is None:
                r.pulled_at = now
                changed = True
        if changed:
            self._db.commit()

    def get_by_request_ids(self, request_ids: list[str]) -> list[PendingActionModel]:
        if not request_ids:
            return []
        return (
            self._db.query(PendingActionModel)
            .filter(PendingActionModel.request_id.in_(request_ids))
            .order_by(PendingActionModel.id.desc())
            .all()
        )

    def ack(self, *, action_id: int, device_id: str, status: str, ack_payload: dict | None = None) -> PendingActionModel | None:
        row = (
            self._db.query(PendingActionModel)
            .filter(PendingActionModel.id == int(action_id))
            .filter(PendingActionModel.device_id == device_id)
            .one_or_none()
        )
        if row is None:
            return None
        row.status = status
        row.ack = ack_payload
        self._db.commit()
        self._db.refresh(row)
        return row


class PlaceRepository:
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distance in meters using Haversine formula."""
        R = 6_371_000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2) + (math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_by_id(self, *, place_id: int) -> PlaceModel | None:
        return self._db.query(PlaceModel).filter(PlaceModel.id == int(place_id)).one_or_none()

    def upsert(
        self,
        *,
        device_id: str,
        title: str,
        lat: float,
        lon: float,
        radius_m: int = 150,
    ) -> PlaceModel:
        title_n = (title or "").strip().lower()
        row = (
            self._db.query(PlaceModel)
            .filter(PlaceModel.device_id == device_id)
            .filter(PlaceModel.title == title_n)
            .one_or_none()
        )
        if row is None:
            # If the new place intersects an existing one (geo overlap), do not create a new row.
            # We treat "пересекается" as: new point falls inside existing place radius.
            # This prevents duplicates from GPS jitter or re-saving the same area with a new title.
            try:
                existing = self.list_by_device(device_id=device_id)
                for p in existing:
                    d = self._haversine_distance_m(float(lat), float(lon), float(p.lat), float(p.lon))
                    if d <= float(p.radius_m or 0):
                        return p
            except Exception:
                # Never block place saving due to overlap calculation errors
                pass
            row = PlaceModel(
                device_id=device_id,
                title=title_n,
                lat=lat,
                lon=lon,
                radius_m=int(radius_m or 150),
                last_seen_at=None,
            )
            self._db.add(row)
        else:
            row.lat = lat
            row.lon = lon
            row.radius_m = int(radius_m or row.radius_m or 150)
        self._db.commit()
        self._db.refresh(row)
        return row

    def get_by_title(self, *, device_id: str, title: str) -> PlaceModel | None:
        title_n = (title or "").strip().lower()
        return (
            self._db.query(PlaceModel)
            .filter(PlaceModel.device_id == device_id)
            .filter(PlaceModel.title == title_n)
            .one_or_none()
        )

    def list_by_device(self, *, device_id: str) -> list[PlaceModel]:
        return self._db.query(PlaceModel).filter(PlaceModel.device_id == device_id).all()

    def list_all(self, *, limit: int = 200, offset: int = 0) -> list[PlaceModel]:
        return (
            self._db.query(PlaceModel)
            .order_by(PlaceModel.id.desc())
            .offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

    def touch_last_seen(self, *, place_id: int, now: datetime) -> None:
        row = self._db.query(PlaceModel).filter(PlaceModel.id == int(place_id)).one_or_none()
        if row is None:
            return
        row.last_seen_at = now
        self._db.commit()

    def update_radius(self, *, place_id: int, radius_m: int) -> PlaceModel | None:
        return self.update(place_id=place_id, radius_m=radius_m, title=None)

    def update(
        self,
        *,
        place_id: int,
        radius_m: int | None = None,
        title: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> PlaceModel | None:
        row = self.get_by_id(place_id=place_id)
        if row is None:
            return None
        if radius_m is not None:
            row.radius_m = int(radius_m)
        if lat is not None:
            row.lat = float(lat)
        if lon is not None:
            row.lon = float(lon)
        if title is not None:
            title_n = (title or "").strip().lower()
            if not title_n:
                raise ValueError("invalid_title")
            if title_n != row.title:
                conflict = (
                    self._db.query(PlaceModel)
                    .filter(PlaceModel.device_id == row.device_id)
                    .filter(PlaceModel.title == title_n)
                    .one_or_none()
                )
                if conflict is not None and int(conflict.id) != int(row.id):
                    raise ValueError("title_conflict")
                row.title = title_n
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise ValueError("title_conflict")
        self._db.refresh(row)
        return row

    def delete(self, *, place_id: int) -> bool:
        row = self.get_by_id(place_id=place_id)
        if row is None:
            return False
        # No FK constraints in schema: delete children explicitly.
        self._db.query(PlaceReminderModel).filter(PlaceReminderModel.place_id == int(place_id)).delete(
            synchronize_session=False
        )
        self._db.delete(row)
        self._db.commit()
        return True


class PlaceReminderRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        place_id: int,
        text: str,
        event: str = "enter",
        active: bool = True,
    ) -> PlaceReminderModel:
        ev = (event or "enter").strip().lower()
        if ev not in ("enter", "exit"):
            ev = "enter"
        row = PlaceReminderModel(
            place_id=int(place_id),
            text=(text or "").strip(),
            event=ev,
            active=bool(active),
            last_fired_at=None,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_active_by_place(self, *, place_id: int, event: str) -> list[PlaceReminderModel]:
        ev = (event or "enter").strip().lower()
        return (
            self._db.query(PlaceReminderModel)
            .filter(PlaceReminderModel.place_id == int(place_id))
            .filter(PlaceReminderModel.active.is_(True))
            .filter(PlaceReminderModel.event == ev)
            .all()
        )

    def mark_fired(self, *, reminder_id: int, now: datetime) -> None:
        row = self._db.query(PlaceReminderModel).filter(PlaceReminderModel.id == int(reminder_id)).one_or_none()
        if row is None:
            return
        row.last_fired_at = now
        self._db.commit()


class DeviceLocationRepository:
    def __init__(self, db: Session):
        self._db = db

    def get(self, *, device_id: str) -> DeviceLastLocationModel | None:
        return (
            self._db.query(DeviceLastLocationModel)
            .filter(DeviceLastLocationModel.device_id == device_id)
            .one_or_none()
        )

    def upsert(self, *, device_id: str, lat: float, lon: float, ts: datetime) -> None:
        row = self.get(device_id=device_id)
        if row is None:
            row = DeviceLastLocationModel(device_id=device_id, lat=lat, lon=lon, ts=ts)
            self._db.add(row)
        else:
            row.lat = lat
            row.lon = lon
            row.ts = ts
        self._db.commit()


class TaskRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        device_id: str,
        text: str,
        urgent: bool,
        important: bool,
        category: str,
        due_date: date | None = None,
        now: datetime,
    ) -> TaskModel:
        row = TaskModel(
            device_id=device_id,
            text=(text or "").strip(),
            category=(category or "прочее").strip().lower()[:64],
            urgent=bool(urgent),
            important=bool(important),
            status="active",
            due_date=due_date,
            completed_at=None,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list(
        self,
        *,
        device_id: str | None = None,
        status: str | None = "active",
        limit: int = 200,
        offset: int = 0,
    ) -> list[TaskModel]:
        q = self._db.query(TaskModel)
        if device_id:
            q = q.filter(TaskModel.device_id == device_id)
        if status:
            q = q.filter(TaskModel.status == status)
        # For "по порядку": active -> oldest first, done -> newest first
        if status == "active":
            q = q.order_by(TaskModel.id.asc())
        else:
            q = q.order_by(TaskModel.id.desc())
        return (
            q.offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

    def get(self, *, task_id: int) -> TaskModel | None:
        return self._db.query(TaskModel).filter(TaskModel.id == int(task_id)).one_or_none()

    def update(
        self,
        *,
        task_id: int,
        text: str | None = None,
        urgent: bool | None = None,
        important: bool | None = None,
        category: str | None = None,
        due_date: date | None = None,
    ) -> TaskModel | None:
        row = self.get(task_id=task_id)
        if row is None:
            return None
        if text is not None:
            row.text = (text or "").strip()
        if urgent is not None:
            row.urgent = bool(urgent)
        if important is not None:
            row.important = bool(important)
        if category is not None:
            row.category = (category or "прочее").strip().lower()[:64]
        if due_date is not None:
            row.due_date = due_date
        self._db.commit()
        self._db.refresh(row)
        return row

    def mark_done(self, *, task_id: int, now: datetime) -> TaskModel | None:
        row = self.get(task_id=task_id)
        if row is None:
            return None
        row.status = "done"
        row.completed_at = now
        self._db.commit()
        self._db.refresh(row)
        return row


class TaskCategoryRepository:
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _norm(title: str) -> str:
        t = (title or "").strip().lower()
        return (t or "прочее")[:64]

    def upsert(self, *, device_id: str, title: str) -> TaskCategoryModel:
        title_n = self._norm(title)
        row = (
            self._db.query(TaskCategoryModel)
            .filter(TaskCategoryModel.device_id == device_id)
            .filter(TaskCategoryModel.title == title_n)
            .one_or_none()
        )
        if row is None:
            row = TaskCategoryModel(device_id=device_id, title=title_n)
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        return row

    def list(self, *, device_id: str, limit: int = 200, offset: int = 0) -> list[TaskCategoryModel]:
        return (
            self._db.query(TaskCategoryModel)
            .filter(TaskCategoryModel.device_id == device_id)
            .order_by(TaskCategoryModel.title.asc())
            .offset(max(0, int(offset)))
            .limit(min(500, max(1, int(limit))))
            .all()
        )

    def rename(self, *, category_id: int, device_id: str, title: str) -> TaskCategoryModel | None:
        row = (
            self._db.query(TaskCategoryModel)
            .filter(TaskCategoryModel.id == int(category_id))
            .filter(TaskCategoryModel.device_id == device_id)
            .one_or_none()
        )
        if row is None:
            return None
        row.title = self._norm(title)
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete(self, *, category_id: int, device_id: str) -> bool:
        row = (
            self._db.query(TaskCategoryModel)
            .filter(TaskCategoryModel.id == int(category_id))
            .filter(TaskCategoryModel.device_id == device_id)
            .one_or_none()
        )
        if row is None:
            return False
        self._db.delete(row)
        self._db.commit()
        return True
