"""Memory retention policies (domain logic)."""

from datetime import datetime, timedelta


def should_retain_episodic(created_at: datetime, now: datetime) -> bool:
    """Check if episodic memory should be retained."""
    age_days = (now - created_at).days
    return age_days <= 90  # Keep for 90 days


def should_summarize(created_at: datetime, now: datetime) -> bool:
    """Check if memory should be summarized."""
    age_days = (now - created_at).days
    return age_days >= 7  # Summarize after 7 days
