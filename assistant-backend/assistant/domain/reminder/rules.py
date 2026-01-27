from datetime import datetime


def ensure_future(due_at: datetime, now: datetime) -> None:
    if due_at <= now:
        raise ValueError("due_at must be in the future")


def ensure_radius(radius_m: int) -> None:
    if radius_m <= 0 or radius_m > 50_000:
        raise ValueError("radius_m out of range")

