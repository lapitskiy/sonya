from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from dateutil import tz
from dateutil.parser import parse as dt_parse


@dataclass
class Intent:
    name: str
    payload: dict


def parse_intent(text: str, now: datetime | None = None) -> Intent:
    """
    MVP парсер:
    - "напомни через 10 минут ..."
    - "напомни в 18:30 ..."
    - "когда буду рядом с <lat>,<lon> ..."
    """
    t = (text or "").strip().lower()
    now = now or datetime.now(tz=tz.tzutc())

    m = re.search(r"напомни\s+через\s+(\d+)\s*(минут|мин|m)\b", t)
    if m:
        minutes = int(m.group(1))
        due_at = now + timedelta(minutes=minutes)
        return Intent("reminder.create", {"due_at": due_at.isoformat()})

    m = re.search(r"напомни\s+в\s+(\d{1,2}:\d{2})", t)
    if m:
        hhmm = m.group(1)
        base = now.astimezone(tz=tz.tzutc())
        due_at = dt_parse(hhmm, default=base).replace(tzinfo=tz.tzutc())
        if due_at <= now:
            due_at = due_at + timedelta(days=1)
        return Intent("reminder.create", {"due_at": due_at.isoformat()})

    m = re.search(r"рядом\s+с\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)", t)
    if m:
        lat = float(m.group(1))
        lon = float(m.group(3))
        return Intent("geo.create", {"lat": lat, "lon": lon, "radius_m": 150})

    return Intent("unknown", {})

