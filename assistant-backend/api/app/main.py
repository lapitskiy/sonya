import logging
import os
import time
import uuid
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from assistant.contracts.commands import GeoPingIn, VoiceCommandIn
from assistant.infrastructure.db.base import Base
from assistant.infrastructure.db.session import engine
from assistant.infrastructure.db.repositories import (
    DeviceLocationRepository,
    EventRepository,
    PendingActionRepository,
    PlaceReminderRepository,
    PlaceRepository,
    ReminderRepository,
    TaskCategoryRepository,
    TaskRepository,
    VariableRepository,
)
from assistant.infrastructure.db.session import get_db
from assistant.infrastructure.geo.geofence import GeofenceService
from assistant.infrastructure.llm.client import LLMClient
from assistant.use_cases.create_reminder import CreateReminder
from assistant.use_cases.handle_command import HandleCommand
from assistant.use_cases.process_geo_ping import ProcessGeoPing
from assistant.infrastructure.db import models as _models  # noqa: F401


app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# MVP CORS: UI runs on a different port/host, so allow browser requests.
_cors_origins = [
    "http://localhost:13000",
    "http://127.0.0.1:13000",
    "http://192.168.0.50:13000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        origin = request.headers.get("origin")
        method = request.method
        path = request.url.path
        qs = request.url.query
        client_ip = getattr(getattr(request, "client", None), "host", None)
        full_path = path + (("?" + qs) if qs else "")
        logger.info("HTTP %s %s start client=%s origin=%s", method, full_path, client_ip, origin)
        try:
            resp: Response = await call_next(request)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            bytes_out = resp.headers.get("content-length")
            logger.info(
                "HTTP %s %s -> %s dt_ms=%.1f bytes=%s",
                method,
                full_path,
                resp.status_code,
                dt_ms,
                bytes_out,
            )
            return resp
        except Exception:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.exception("HTTP %s %s -> exception dt_ms=%.1f", method, full_path, dt_ms)
            raise


app.add_middleware(_RequestLogMiddleware)

# MVP in-memory session store (cookie -> token payload)
_SESSIONS: dict[str, dict] = {}


class NLUIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    lat: float | None = None
    lon: float | None = None
    device_time: datetime | None = None


class PendingActionCreateIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    payload: dict
    status: str = "pending"
    dedupe_key: str | None = Field(default=None, max_length=128)
    ttl_sec: int = 3600


class PendingActionAckIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    action_id: int
    status: str = Field(min_length=1, max_length=32)  # pending/scheduled/fired/etc
    ack: dict | None = None


class PlaceUpdateIn(BaseModel):
    radius_m: int | None = Field(default=None, ge=10, le=10_000)
    title: str | None = Field(default=None, max_length=128)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class PlaceCreateIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=128)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=150, ge=10, le=10_000)


class TaskCreateIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4096)
    urgent: bool = False
    important: bool = False
    category: str = Field(default="прочее", max_length=64)
    due_date: date | None = None


class TaskUpdateIn(BaseModel):
    text: str | None = Field(default=None, max_length=4096)
    urgent: bool | None = None
    important: bool | None = None
    status: str | None = Field(default=None, max_length=16)  # active/done
    category: str | None = Field(default=None, max_length=64)
    due_date: date | None = None


class TaskCategoryCreateIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=64)


class TaskCategoryUpdateIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=64)


@app.on_event("startup")
def _startup() -> None:
    # Use Alembic migrations (do not auto-create tables on startup).
    return None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/auth/callback")
def auth_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """
    OIDC callback: exchange authorization code for tokens server-side,
    then set cookie for UI (avoids browser WebCrypto dependency).
    """
    keycloak_url = os.getenv("KEYCLOAK_URL", "http://keycloak:8080").rstrip("/")
    realm = os.getenv("KEYCLOAK_REALM", "sonya")
    client_id = os.getenv("KEYCLOAK_CLIENT_ID", "ui-shell")
    client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    redirect_uri = os.getenv("KEYCLOAK_REDIRECT_URI") or str(request.url_for("auth_callback"))
    ui_redirect = os.getenv("UI_REDIRECT_URL")
    if not ui_redirect:
        host = request.url.hostname or "localhost"
        scheme = request.url.scheme or "http"
        ui_port = os.getenv("UI_PORT", "13000")
        ui_redirect = f"{scheme}://{host}:{ui_port}/"

    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    if client_secret:
        form["client_secret"] = client_secret

    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        logger.exception("Keycloak token exchange failed")
        return {"error": "token_exchange_failed", "detail": str(e)}

    # Store tokens for debugging/auditing (events) and session cookie
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {"token_response": raw}

    events = EventRepository(db)
    events.add(
        device_id="web",
        type_="auth.token",
        payload={"session_id": session_id, "token_response_raw": raw},
    )

    resp = RedirectResponse(url=ui_redirect, status_code=302)
    resp.set_cookie(
        key="sonya_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
    )
    # Non-HttpOnly marker cookie for UI JS (so it can detect "logged in" without reading token)
    resp.set_cookie(
        key="sonya_session_present",
        value="1",
        httponly=False,
        samesite="lax",
        path="/",
    )
    return resp


@app.post("/command")
def command(cmd: VoiceCommandIn, db: Session = Depends(get_db)) -> dict:
    cmd_payload = cmd.model_dump() if hasattr(cmd, "model_dump") else cmd.dict()
    logger.info("POST /command payload=%s", cmd_payload)
    repo = ReminderRepository(db)
    events = EventRepository(db)
    vars_repo = VariableRepository(db)
    pending_repo = PendingActionRepository(db)
    places_repo = PlaceRepository(db)
    place_reminders_repo = PlaceReminderRepository(db)
    create_reminder = CreateReminder(repo)
    # LLM config is stored in DB variables (Settings -> Variables)
    # Default scope: "llm"
    scope = "llm"
    provider = (vars_repo.get_value(scope=scope, name="provider", default="mvp") or "mvp").strip()
    provider_l = provider.lower()

    if provider_l == "gigachat":
        api_key = (vars_repo.get_value(scope=scope, name="gigachat_basic_auth_b64", default="") or "").strip()
        model = (vars_repo.get_value(scope=scope, name="gigachat_model", default="GigaChat") or "GigaChat").strip()
        base_url = (
            vars_repo.get_value(
                scope=scope,
                name="gigachat_base_url",
                default="https://gigachat.devices.sberbank.ru/api/v1",
            )
            or "https://gigachat.devices.sberbank.ru/api/v1"
        ).strip()
        oauth_url = (vars_repo.get_value(scope=scope, name="gigachat_oauth_url", default="") or "").strip() or None
        oauth_scope = (vars_repo.get_value(scope=scope, name="gigachat_oauth_scope", default="") or "").strip() or None
        tls_insecure = (vars_repo.get_value(scope=scope, name="gigachat_tls_insecure", default="") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
    else:
        api_key = (vars_repo.get_value(scope=scope, name="deepseek_api_key", default="") or "").strip()
        model = (vars_repo.get_value(scope=scope, name="deepseek_model", default="deepseek-chat") or "deepseek-chat").strip()
        base_url = (
            vars_repo.get_value(scope=scope, name="deepseek_base_url", default="https://api.deepseek.com")
            or "https://api.deepseek.com"
        ).strip()
        oauth_url = None
        oauth_scope = None
        tls_insecure = False
    nlu_prompt = (vars_repo.get_value(scope=scope, name="nlu_system_prompt", default="") or "").strip() or None

    llm = LLMClient(
        api_key=api_key,
        model=model,
        provider=provider,
        base_url=base_url,
        oauth_url=oauth_url,
        oauth_scope=oauth_scope,
        tls_insecure=tls_insecure,
        nlu_system_prompt=nlu_prompt,
    )
    tasks_repo = TaskRepository(db)
    task_categories_repo = TaskCategoryRepository(db)
    uc = HandleCommand(
        llm,
        create_reminder,
        events,
        pending_repo,
        places_repo,
        place_reminders_repo,
        tasks_repo,
        task_categories_repo,
    )

    now = cmd.device_time or datetime.now(timezone.utc)
    intent = uc.execute(cmd, now=now)

    dump = intent.model_dump() if hasattr(intent, "model_dump") else intent.dict()
    return {"intent": dump}


@app.post("/geo-ping")
def geo_ping(body: GeoPingIn, db: Session = Depends(get_db)) -> dict:
    """
    Device sends location periodically. We detect place transitions:
      - enter (outside→inside)
      - exit  (inside→outside)
    and enqueue matching place reminders into pending_actions.
    """
    now = datetime.now(timezone.utc)
    uc = ProcessGeoPing(
        places=PlaceRepository(db),
        place_reminders=PlaceReminderRepository(db),
        device_locations=DeviceLocationRepository(db),
        pending_actions=PendingActionRepository(db),
        geofence=GeofenceService(),
    )
    fired = uc.execute(device_id=body.device_id, lat=body.lat, lon=body.lon, now=now)
    return {"fired": fired}


def _place_to_dict(p) -> dict:
    return {
        "id": int(getattr(p, "id")),
        "device_id": getattr(p, "device_id", None),
        "title": getattr(p, "title", None),
        "lat": getattr(p, "lat", None),
        "lon": getattr(p, "lon", None),
        "radius_m": getattr(p, "radius_m", None),
        "last_seen_at": p.last_seen_at.isoformat() if getattr(p, "last_seen_at", None) else None,
        "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }


def _task_to_dict(t) -> dict:
    return {
        "id": int(getattr(t, "id")),
        "device_id": getattr(t, "device_id", None),
        "text": getattr(t, "text", None),
        "category": getattr(t, "category", None),
        "urgent": bool(getattr(t, "urgent", False)),
        "important": bool(getattr(t, "important", False)),
        "status": getattr(t, "status", None),
        "due_date": t.due_date.isoformat() if getattr(t, "due_date", None) else None,
        "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
        "updated_at": t.updated_at.isoformat() if getattr(t, "updated_at", None) else None,
        "completed_at": t.completed_at.isoformat() if getattr(t, "completed_at", None) else None,
    }


def _task_category_to_dict(c) -> dict:
    return {
        "id": int(getattr(c, "id")),
        "device_id": getattr(c, "device_id", None),
        "title": getattr(c, "title", None),
        "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
        "updated_at": c.updated_at.isoformat() if getattr(c, "updated_at", None) else None,
    }


@app.get("/places")
def list_places(
    device_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    repo = PlaceRepository(db)
    if device_id:
        rows = repo.list_by_device(device_id=device_id)
    else:
        rows = repo.list_all(limit=limit, offset=offset)
    return {"items": [_place_to_dict(r) for r in rows]}


@app.post("/places")
def create_place(body: PlaceCreateIn, db: Session = Depends(get_db)) -> dict:
    repo = PlaceRepository(db)
    # Use repository upsert semantics: (device_id + title) unique, coords/radius are updated if exists.
    row = repo.upsert(
        device_id=body.device_id,
        title=body.title,
        lat=body.lat,
        lon=body.lon,
        radius_m=body.radius_m,
    )
    return {"item": _place_to_dict(row)}


@app.put("/places/{place_id}")
def update_place(place_id: int, body: PlaceUpdateIn, db: Session = Depends(get_db)) -> dict:
    repo = PlaceRepository(db)
    try:
        row = repo.update(
            place_id=place_id,
            radius_m=body.radius_m,
            title=body.title,
            lat=body.lat,
            lon=body.lon,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "invalid_title":
            raise HTTPException(status_code=422, detail="invalid title")
        if msg == "title_conflict":
            raise HTTPException(status_code=409, detail="place title already exists for this device")
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="place not found")
    return {"item": _place_to_dict(row)}


@app.delete("/places/{place_id}")
def delete_place(place_id: int, db: Session = Depends(get_db)) -> dict:
    repo = PlaceRepository(db)
    ok = repo.delete(place_id=int(place_id))
    if not ok:
        raise HTTPException(status_code=404, detail="place not found")
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks(
    device_id: str | None = None,
    status: str = "active",
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    repo = TaskRepository(db)
    st = (status or "active").strip().lower()
    if st not in ("active", "done"):
        st = "active"
    rows = repo.list(device_id=device_id, status=st, limit=limit, offset=offset)
    return {"items": [_task_to_dict(r) for r in rows]}


@app.post("/tasks")
def create_task(body: TaskCreateIn, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    repo = TaskRepository(db)
    cats = TaskCategoryRepository(db)
    cats.upsert(device_id=body.device_id, title=body.category)
    row = repo.create(
        device_id=body.device_id,
        text=body.text,
        urgent=bool(body.urgent),
        important=bool(body.important),
        category=body.category,
        due_date=body.due_date,
        now=now,
    )
    return {"item": _task_to_dict(row)}


@app.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdateIn, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    repo = TaskRepository(db)
    st = (body.status or "").strip().lower() if body.status is not None else None
    if st == "done":
        row = repo.mark_done(task_id=int(task_id), now=now)
    else:
        row = repo.update(
            task_id=int(task_id),
            text=body.text,
            urgent=body.urgent,
            important=body.important,
            category=body.category,
            due_date=body.due_date,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")
    if body.category is not None:
        TaskCategoryRepository(db).upsert(device_id=row.device_id, title=row.category)
    return {"item": _task_to_dict(row)}


@app.get("/task-categories")
def list_task_categories(device_id: str, limit: int = 200, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    repo = TaskCategoryRepository(db)
    rows = repo.list(device_id=device_id, limit=limit, offset=offset)
    return {"items": [_task_category_to_dict(r) for r in rows]}


@app.post("/task-categories")
def create_task_category(body: TaskCategoryCreateIn, db: Session = Depends(get_db)) -> dict:
    repo = TaskCategoryRepository(db)
    row = repo.upsert(device_id=body.device_id, title=body.title)
    return {"item": _task_category_to_dict(row)}


@app.put("/task-categories/{category_id}")
def rename_task_category(category_id: int, body: TaskCategoryUpdateIn, db: Session = Depends(get_db)) -> dict:
    old_row = (
        db.query(_models.TaskCategoryModel)
        .filter(_models.TaskCategoryModel.id == int(category_id))
        .filter(_models.TaskCategoryModel.device_id == body.device_id)
        .one_or_none()
    )
    if old_row is None:
        raise HTTPException(status_code=404, detail="category not found")
    old_title = old_row.title
    new_title = (body.title or "").strip().lower()[:64] or "прочее"
    old_row.title = new_title
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # If category already exists, keep idempotent behavior
        pass
    # propagate rename into tasks (simple string category storage)
    db.query(_models.TaskModel).filter(_models.TaskModel.device_id == body.device_id).filter(
        _models.TaskModel.category == old_title
    ).update({_models.TaskModel.category: new_title}, synchronize_session=False)
    db.commit()
    row = (
        db.query(_models.TaskCategoryModel)
        .filter(_models.TaskCategoryModel.device_id == body.device_id)
        .filter(_models.TaskCategoryModel.title == new_title)
        .one_or_none()
    )
    return {"item": _task_category_to_dict(row)}


@app.delete("/task-categories/{category_id}")
def delete_task_category(category_id: int, device_id: str, db: Session = Depends(get_db)) -> dict:
    repo = TaskCategoryRepository(db)
    ok = repo.delete(category_id=int(category_id), device_id=device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="category not found")
    return {"status": "ok"}


@app.post("/nlu")
def nlu(body: NLUIn, db: Session = Depends(get_db)) -> dict:
    """
    Raw NLU endpoint: returns JSON produced by LLM (DeepSeek/GigaChat/etc).
    Uses Variables (scope=llm) for config.
    """
    vars_repo = VariableRepository(db)
    scope = "llm"
    provider = (vars_repo.get_value(scope=scope, name="provider", default="mvp") or "mvp").strip()
    provider_l = provider.lower()

    if provider_l == "gigachat":
        api_key = (vars_repo.get_value(scope=scope, name="gigachat_basic_auth_b64", default="") or "").strip()
        model = (vars_repo.get_value(scope=scope, name="gigachat_model", default="GigaChat") or "GigaChat").strip()
        base_url = (
            vars_repo.get_value(
                scope=scope,
                name="gigachat_base_url",
                default="https://gigachat.devices.sberbank.ru/api/v1",
            )
            or "https://gigachat.devices.sberbank.ru/api/v1"
        ).strip()
        oauth_url = (vars_repo.get_value(scope=scope, name="gigachat_oauth_url", default="") or "").strip() or None
        oauth_scope = (vars_repo.get_value(scope=scope, name="gigachat_oauth_scope", default="") or "").strip() or None
        tls_insecure = (vars_repo.get_value(scope=scope, name="gigachat_tls_insecure", default="") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
    else:
        api_key = (vars_repo.get_value(scope=scope, name="deepseek_api_key", default="") or "").strip()
        model = (vars_repo.get_value(scope=scope, name="deepseek_model", default="deepseek-chat") or "deepseek-chat").strip()
        base_url = (
            vars_repo.get_value(scope=scope, name="deepseek_base_url", default="https://api.deepseek.com")
            or "https://api.deepseek.com"
        ).strip()
        oauth_url = None
        oauth_scope = None
        tls_insecure = False
    nlu_prompt = (vars_repo.get_value(scope=scope, name="nlu_system_prompt", default="") or "").strip() or None

    llm = LLMClient(
        api_key=api_key,
        model=model,
        provider=provider,
        base_url=base_url,
        oauth_url=oauth_url,
        oauth_scope=oauth_scope,
        tls_insecure=tls_insecure,
        nlu_system_prompt=nlu_prompt,
    )
    out = llm.extract_nlu_json(body.text, lat=body.lat, lon=body.lon, now=body.device_time)
    return {"nlu": out}


def _pending_action_to_dict(r) -> dict:
    return {
        "id": int(r.id),
        "device_id": r.device_id,
        "action_type": getattr(r, "action_type", None),
        "dedupe_key": getattr(r, "dedupe_key", None),
        "request_id": getattr(r, "request_id", None),
        "status": r.status,
        "payload": r.payload,
        "ack": r.ack,
        "pulled_at": r.pulled_at.isoformat() if getattr(r, "pulled_at", None) else None,
        "expires_at": r.expires_at.isoformat() if getattr(r, "expires_at", None) else None,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
    }


def _normalize_action_payload(action_type: str, payload: dict) -> dict:
    """
    Normalize internal payload to Android contract:
      - always has type + time
      - timer/text-timer: time is ISO-8601 duration (PT..)
      - alarm/approx-alarm: time is ISO-8601 datetime (with timezone)
    We keep extra fields like text/interest if present.
    """
    p = payload or {}
    typ = str(action_type or p.get("type") or "unknown")
    out: dict = {"type": typ}

    # Preferred: payload.time
    t = p.get("time")
    # Backward-compat:
    # - timer example previously used "0:0:10"
    # - alarm example sometimes had separate "date" + "time"
    if t is None and p.get("date") and p.get("time"):
        t = f"{p.get('date')} {p.get('time')}"
    if isinstance(t, str):
        out["time"] = t

    # Optional extras
    if "text" in p:
        out["text"] = p.get("text")
    if "interest" in p:
        out["interest"] = p.get("interest")
    if "lat" in p:
        out["lat"] = p.get("lat")
    if "lon" in p:
        out["lon"] = p.get("lon")
    if "radius_m" in p:
        out["radius_m"] = p.get("radius_m")
    return out


def _pending_action_to_android_item(r) -> dict:
    """
    Public contract for Android pull: minimal fields + normalized payload.
    """
    return {
        "id": int(r.id),
        **_normalize_action_payload(getattr(r, "action_type", "unknown"), r.payload),
    }


@app.get("/pending-actions")
def pending_actions(device_id: str, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    t0 = time.perf_counter()
    repo = PendingActionRepository(db)
    t_repo = time.perf_counter()
    rows = repo.list_pending(device_id=device_id, limit=limit, offset=offset)
    t_list = time.perf_counter()
    # mark that device pulled these actions (but keep them pending until /ack)
    repo.mark_pulled(action_ids=[int(r.id) for r in rows])
    t_mark = time.perf_counter()
    # Android-facing contract (no internal fields)
    items = [_pending_action_to_android_item(r) for r in rows]
    t_build = time.perf_counter()
    logger.info(
        "GET /pending-actions device_id=%s rows=%d t_repo_ms=%.1f t_list_ms=%.1f t_mark_ms=%.1f t_build_ms=%.1f t_total_ms=%.1f",
        device_id,
        len(rows),
        (t_repo - t0) * 1000.0,
        (t_list - t_repo) * 1000.0,
        (t_mark - t_list) * 1000.0,
        (t_build - t_mark) * 1000.0,
        (t_build - t0) * 1000.0,
    )
    return {"items": items}


@app.post("/ack")
def ack(body: PendingActionAckIn, db: Session = Depends(get_db)) -> dict:
    logger.info("POST /ack device_id=%s action_id=%d status=%s ack=%s", 
                body.device_id, body.action_id, body.status, body.ack)
    repo = PendingActionRepository(db)
    row = repo.ack(action_id=body.action_id, device_id=body.device_id, status=body.status, ack_payload=body.ack)
    if row is None:
        logger.warning("POST /ack: pending action %d not found for device %s", body.action_id, body.device_id)
        raise HTTPException(status_code=404, detail="pending action not found")
    return {"status": "ok"}


@app.post("/debug/pending-actions")
def debug_create_pending_action(body: PendingActionCreateIn, db: Session = Depends(get_db)) -> dict:
    """
    Debug helper: manually create a pending action so Android can fetch it via GET /pending-actions.
    """
    repo = PendingActionRepository(db)
    action_type = str((body.payload or {}).get("type") or "unknown")
    # Minimal contract validation for common actions
    if action_type == "timer":
        t = (body.payload or {}).get("time")
        if not isinstance(t, str) or not t:
            raise HTTPException(status_code=422, detail="timer requires payload.time (e.g. PT10S)")
        if not t.startswith("P"):
            raise HTTPException(status_code=422, detail="timer payload.time must be ISO-8601 duration (e.g. PT10S)")
    row = repo.create(
        device_id=body.device_id,
        action_type=action_type,
        payload=body.payload,
        status=body.status,
        dedupe_key=body.dedupe_key,
        ttl_sec=body.ttl_sec,
    )
    return {"item": _pending_action_to_dict(row)}


@app.get("/events/commands")
def list_command_events(
    device_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    return _list_command_requests(device_id=device_id, limit=limit, offset=offset, db=db)


def _list_command_requests(*, device_id: str | None, limit: int, offset: int, db: Session) -> dict:
    t0 = time.perf_counter()
    events = EventRepository(db)
    rows = events.list_events(type_="command.received", device_id=device_id, limit=limit, offset=offset)
    t_events = time.perf_counter()
    # Enrich with pending-action status by request_id (for UI).
    req_ids: list[str] = []
    for r in rows:
        rid = None
        try:
            rid = (r.payload or {}).get("request_id")
        except Exception:
            rid = None
        if isinstance(rid, str) and rid:
            req_ids.append(rid)
    pa_repo = PendingActionRepository(db)
    pa_rows = pa_repo.get_by_request_ids(req_ids)
    t_pa = time.perf_counter()
    pa_by_req: dict[str, dict] = {}
    for pa in pa_rows:
        if pa.request_id and pa.request_id not in pa_by_req:
            pa_by_req[pa.request_id] = _pending_action_to_dict(pa)
    out = {
        "items": [
            {
                "id": r.id,
                "device_id": r.device_id,
                "type": r.type,
                "delivered": bool(r.delivered),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "payload": r.payload,
                "pending_action": pa_by_req.get((r.payload or {}).get("request_id"))
                if isinstance((r.payload or {}).get("request_id"), str)
                else None,
            }
            for r in rows
        ]
    }
    t_build = time.perf_counter()
    logger.info(
        "GET /what-said/requests device_id=%s rows=%d req_ids=%d pa_rows=%d t_events_ms=%.1f t_pa_ms=%.1f t_build_ms=%.1f t_total_ms=%.1f",
        device_id,
        len(rows),
        len(req_ids),
        len(pa_rows),
        (t_events - t0) * 1000.0,
        (t_pa - t_events) * 1000.0,
        (t_build - t_pa) * 1000.0,
        (t_build - t0) * 1000.0,
    )
    return out


@app.get("/what-said/requests")
def what_said_requests(
    device_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """UI contract for "What said" module: list command requests + optional pending_action by request_id."""
    return _list_command_requests(device_id=device_id, limit=limit, offset=offset, db=db)


class VariableUpsertIn(BaseModel):
    scope: str = Field(min_length=1, max_length=64)
    # Title is a UI label; allow empty (UI may omit it).
    title: str = Field(default="", max_length=128)
    name: str = Field(min_length=1, max_length=128)
    value_type: str = Field(default="string", max_length=32)
    value: str = ""


def _variable_to_dict(r) -> dict:
    return {
        "id": int(r.id),
        "scope": r.scope,
        "title": r.title,
        "name": r.name,
        "value_type": r.value_type,
        "value": r.value,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
    }


@app.get("/settings/variables")
def list_variables(
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    repo = VariableRepository(db)
    rows = repo.list(limit=limit, offset=offset)
    return {"items": [_variable_to_dict(r) for r in rows]}


@app.post("/settings/variables")
def create_variable(body: VariableUpsertIn, db: Session = Depends(get_db)) -> dict:
    repo = VariableRepository(db)
    try:
        row = repo.create(
            scope=body.scope,
            title=body.title,
            name=body.name,
            value_type=body.value_type,
            value=body.value,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Variable with the same scope+name already exists")
    return {"item": _variable_to_dict(row)}


@app.put("/settings/variables/{variable_id}")
def update_variable(variable_id: int, body: VariableUpsertIn, db: Session = Depends(get_db)) -> dict:
    repo = VariableRepository(db)
    try:
        row = repo.update(
            variable_id=variable_id,
            scope=body.scope,
            title=body.title,
            name=body.name,
            value_type=body.value_type,
            value=body.value,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Variable with the same scope+name already exists")
    if row is None:
        raise HTTPException(status_code=404, detail="Variable not found")
    return {"item": _variable_to_dict(row)}

