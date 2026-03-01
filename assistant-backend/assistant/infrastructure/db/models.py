from datetime import date

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ReminderModel(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    due_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    fired: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeoTriggerModel(Base):
    __tablename__ = "geo_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column()
    lon: Mapped[float] = mapped_column()
    radius_m: Mapped[int] = mapped_column(Integer, default=150)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VariableModel(Base):
    __tablename__ = "variables"
    __table_args__ = (UniqueConstraint("scope", "name", name="uq_variables_scope_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    scope: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128), index=True)

    value_type: Mapped[str] = mapped_column(String(32), default="string")
    value: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PendingActionModel(Base):
    __tablename__ = "pending_actions"
    __table_args__ = (UniqueConstraint("device_id", "dedupe_key", name="uq_pending_actions_device_dedupe"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    # Correlation id from command.received payload.request_id
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # Explicit action type (e.g. timer/alarm/geo/...)
    action_type: Mapped[str] = mapped_column(String(64), index=True, default="unknown")
    # Idempotency key: unique per device (prevents duplicates on retries).
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    payload: Mapped[dict] = mapped_column(JSONB)
    ack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pulled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlaceModel(Base):
    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("device_id", "title", name="uq_places_device_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(128), index=True)  # e.g. "дом", "работа"

    lat: Mapped[float] = mapped_column()
    lon: Mapped[float] = mapped_column()
    radius_m: Mapped[int] = mapped_column(Integer, default=150)

    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlaceReminderModel(Base):
    __tablename__ = "place_reminders"
    __table_args__ = (UniqueConstraint("place_id", "text", "event", name="uq_place_reminders_place_text_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_id: Mapped[int] = mapped_column(Integer, index=True)

    # "enter" (outside→inside) or "exit" (inside→outside)
    event: Mapped[str] = mapped_column(String(8), default="enter", index=True)
    text: Mapped[str] = mapped_column(Text)

    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_fired_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class DeviceLastLocationModel(Base):
    __tablename__ = "device_last_locations"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lat: Mapped[float] = mapped_column()
    lon: Mapped[float] = mapped_column()
    ts: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)

    category: Mapped[str] = mapped_column(String(64), default="прочее", index=True)
    urgent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    important: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active/done

    # Optional "day task" marker: which calendar day this task belongs to (no time).
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskCategoryModel(Base):
    __tablename__ = "task_categories"
    __table_args__ = (UniqueConstraint("device_id", "title", name="uq_task_categories_device_title"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(64), index=True)  # stored normalized (lowercase)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

