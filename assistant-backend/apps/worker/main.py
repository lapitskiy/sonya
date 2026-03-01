"""Worker main loop (background tasks)."""

import os
import time
from datetime import datetime, timezone

from assistant.infrastructure.db.session import get_db
from assistant.use_cases.evaluate_geo import EvaluateGeo
from assistant.use_cases.notify_user import NotifyUser
from assistant.infrastructure.db.repositories import EventRepository, ReminderRepository
from assistant.infrastructure.geo.geofence import GeofenceService
from assistant.infrastructure.notifications.push_gateway import PushGateway
from assistant.domain.reminder import should_fire


def worker_loop():
    """Main worker loop."""
    poll_seconds = int(os.getenv("WORKER_POLL_SECONDS", "2"))
    
    # Initialize dependencies
    db = next(get_db())
    reminder_repo = ReminderRepository(db)
    events = EventRepository(db)
    geofence = GeofenceService()
    push_gateway = PushGateway(events)
    
    evaluate_geo = EvaluateGeo(reminder_repo, geofence)
    notify_user = NotifyUser(push_gateway)
    
    while True:
        now = datetime.now(timezone.utc)
        
        # Check time-based reminders
        due_reminders = reminder_repo.find_due_not_fired(now)
        for reminder in due_reminders:
            if should_fire(reminder, now):
                notify_user.execute(reminder, now)
                reminder_repo.mark_fired(reminder_id=reminder.id.value)
        
        # Geo triggers are evaluated via API endpoint /geo-ping
        
        time.sleep(poll_seconds)


if __name__ == "__main__":
    worker_loop()
