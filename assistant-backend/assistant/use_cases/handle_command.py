"""Handle voice command use case."""

from datetime import date, datetime, timedelta, timezone
import json
from uuid import uuid4

from dateutil.parser import parse as dt_parse

from ..contracts.commands import VoiceCommandIn
from ..contracts.intents import Intent
from ..infrastructure.llm.client import LLMClient
from ..infrastructure.db.repositories import (
    EventRepository,
    PendingActionRepository,
    PlaceReminderRepository,
    PlaceRepository,
    TaskCategoryRepository,
    TaskRepository,
)
from .create_reminder import CreateReminder


class HandleCommand:
    """Use case: handle voice command."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        create_reminder: CreateReminder,
        event_repo: EventRepository,
        pending_repo: PendingActionRepository,
        places: PlaceRepository,
        place_reminders: PlaceReminderRepository,
        tasks: TaskRepository,
        task_categories: TaskCategoryRepository,
    ):
        self.llm_client = llm_client
        self.create_reminder = create_reminder
        self.event_repo = event_repo
        self.pending_repo = pending_repo
        self.places = places
        self.place_reminders = place_reminders
        self.tasks = tasks
        self.task_categories = task_categories
    
    def execute(self, cmd: VoiceCommandIn, now: datetime) -> Intent:
        """Execute use case."""
        # Important: payload is stored into JSONB; ensure everything is JSON-serializable
        # (e.g. datetime -> ISO string)
        if hasattr(cmd, "model_dump"):
            cmd_payload = cmd.model_dump(mode="json")  # Pydantic v2
        else:
            cmd_payload = json.loads(cmd.json())       # Pydantic v1
        request_id = str(uuid4())

        # Raw NLU JSON (used for pending_actions + task/place side effects).
        # Also derive internal Intent deterministically from it (avoid extra LLM call).
        try:
            nlu_raw = self.llm_client.extract_nlu_json(cmd.text, lat=cmd.lat, lon=cmd.lon, now=now)
        except Exception:
            nlu_raw = {"type": "unknown"}
        try:
            intent = self.llm_client.intent_from_nlu_json(nlu_raw, lat=cmd.lat, lon=cmd.lon, now=now)
        except Exception:
            intent = self.llm_client.extract_intent(cmd.text, lat=cmd.lat, lon=cmd.lon, now=now)

        # Side effects from raw NLU:
        # - memory-geo: save/update place by current coords
        # - geo-alarm: save place reminder (enter/exit) bound to existing place by title
        # - task: save todo item into DB (Eisenhower urgent/important)
        try:
            nlu_type = str((nlu_raw or {}).get("type") or "unknown").strip().lower()
            if nlu_type == "memory-geo":
                title = str((nlu_raw or {}).get("text") or "").strip()
                if title and (cmd.lat is not None) and (cmd.lon is not None):
                    radius_m = int((nlu_raw or {}).get("radius_m") or 150)
                    self.places.upsert(
                        device_id=cmd.device_id,
                        title=title,
                        lat=float(cmd.lat),
                        lon=float(cmd.lon),
                        radius_m=radius_m,
                    )
            elif nlu_type == "geo-alarm":
                place_title = str((nlu_raw or {}).get("place") or "").strip()
                text = str((nlu_raw or {}).get("text") or "").strip()
                event = str((nlu_raw or {}).get("event") or "enter").strip().lower()
                if place_title and text:
                    place = self.places.get_by_title(device_id=cmd.device_id, title=place_title)
                    if place is None:
                        self.event_repo.add(
                            device_id=cmd.device_id,
                            type_="geo-alarm.place_missing",
                            payload={"place": place_title, "text": text, "event": event},
                        )
                    else:
                        self.place_reminders.create(place_id=int(place.id), text=text, event=event, active=True)
            elif nlu_type == "task":
                text = str((nlu_raw or {}).get("text") or "").strip()
                urgent = bool((nlu_raw or {}).get("urgent") is True)
                important = bool((nlu_raw or {}).get("important") is True)
                if text:
                    category = str((nlu_raw or {}).get("category") or "").strip().lower()
                    due_date: date | None = None
                    raw_due = (nlu_raw or {}).get("due_date")
                    if isinstance(raw_due, str) and raw_due.strip():
                        try:
                            due_date = dt_parse(raw_due.strip()).date()
                        except Exception:
                            due_date = None
                    if due_date is None:
                        t = (cmd.text or "").lower()
                        base = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=timezone.utc)
                        if "послезавтра" in t:
                            due_date = (base + timedelta(days=2)).date()
                        elif "завтра" in t:
                            due_date = (base + timedelta(days=1)).date()
                        elif "сегодня" in t:
                            due_date = base.date()
                    if not category:
                        t = (cmd.text or "").lower()
                        if any(x in t for x in ("дом", "дома", "по дому", "убор", "помыть", "пылесос")):
                            category = "дом"
                        elif any(x in t for x in ("магазин", "покуп", "продукт", "купить")):
                            category = "покупки"
                        elif any(x in t for x in ("работ", "проект", "заказчик", "клиент")):
                            category = "работа"
                        else:
                            category = "прочее"
                    self.task_categories.upsert(device_id=cmd.device_id, title=category)
                    self.tasks.create(
                        device_id=cmd.device_id,
                        text=text,
                        urgent=urgent,
                        important=important,
                        category=category,
                        due_date=due_date,
                        now=now,
                    )
        except Exception:
            # Keep command flow resilient: place features must not break basic NLU.
            pass

        # Create pending action for device (Android pulls it).
        pending_action_id: int | None = None
        try:
            def _normalize_alarm_time_if_past(time_str: str) -> str:
                base = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=timezone.utc)
                try:
                    dt = dt_parse(time_str, default=base)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=base.tzinfo)
                except Exception:
                    return time_str
                t = (cmd.text or "").lower()

                # Heuristic: "сегодня в 9" when it's already evening usually means 21:00 (not 09:00),
                # so if LLM shifted to tomorrow morning, try "today + 12h" first.
                if "сегодня" in t and ("утром" not in t) and base.hour >= 18:
                    try:
                        is_tomorrow = dt.date() == (base + timedelta(days=1)).date()
                        if is_tomorrow and 1 <= int(dt.hour) <= 11:
                            cand = dt.replace(year=base.year, month=base.month, day=base.day, hour=int(dt.hour) + 12)
                            if cand > base:
                                return cand.isoformat()
                    except Exception:
                        pass

                if dt > base:
                    return dt.isoformat()
                if "послезавтра" in t:
                    dt = dt + timedelta(days=2)
                elif "завтра" in t:
                    dt = dt + timedelta(days=1)
                else:
                    dt = base + timedelta(hours=1)
                return dt.isoformat()

            action_type = str((nlu_raw or {}).get("type") or "unknown")
            if action_type not in ("unknown", "task"):
                # Store "clean" android payload into pending_actions (type+time+...),
                # so Android doesn't need to understand internal DB schema.
                action_payload = dict(nlu_raw or {})
                # Contract enforcement: for some action types, payload.time must exist.
                # LLMs sometimes omit it; we prefer producing a valid payload over dropping the action.
                need_time = action_type in ("timer", "text-timer", "alarm", "approx-alarm")
                t = action_payload.get("time")
                if need_time and (not isinstance(t, str) or not t.strip()):
                    # If we don't know exact time, pick a reasonable future default.
                    if action_type in ("timer", "text-timer"):
                        action_payload["time"] = "PT30M"
                    else:
                        base = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=timezone.utc)
                        action_payload["time"] = (base + timedelta(hours=1)).isoformat()
                elif action_type in ("alarm", "approx-alarm") and isinstance(t, str) and t.strip():
                    action_payload["time"] = _normalize_alarm_time_if_past(t.strip())
                row = self.pending_repo.create(
                    device_id=cmd.device_id,
                    action_type=action_type,
                    payload=action_payload,
                    status="pending",
                    dedupe_key=request_id,
                    request_id=request_id,
                )
                pending_action_id = int(row.id)
        except Exception:
            pending_action_id = None

        if hasattr(intent, "model_dump"):
            intent_payload = intent.model_dump(mode="json")  # Pydantic v2
        else:
            intent_payload = json.loads(intent.json())       # Pydantic v1

        # Persist everything we received (and the parsed intent) as an event
        self.event_repo.add(
            device_id=cmd.device_id,
            type_="command.received",
            payload={
                "request_id": request_id,
                "received": cmd_payload,     # text, lat/lon, device_time
                "effective_now": now.isoformat(),
                "intent": intent_payload,
                "nlu": nlu_raw,
                "pending_action_id": pending_action_id,
            },
        )
        
        # If it's a reminder intent, create reminder
        if intent.type in ("time", "geo"):
            self.create_reminder.execute(
                device_id=cmd.device_id,
                intent=intent,
                text=cmd.text,
                now=now,
            )
        
        return intent
