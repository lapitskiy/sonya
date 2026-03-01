"""Create reminder use case."""

from datetime import datetime

from ..contracts.intents import Intent
from ..domain.reminder import Reminder, ReminderId, ReminderStatus, validate_trigger
from ..domain.reminder.value_objects import GeoTrigger, TimeTrigger
from ..infrastructure.db.repositories import ReminderRepository


class CreateReminder:
    """Use case: create a reminder from intent."""
    
    def __init__(self, repository: ReminderRepository):
        self.repository = repository
    
    def execute(self, device_id: str, intent: Intent, text: str, now: datetime) -> Reminder:
        """Execute use case."""
        # Convert contract intent to domain trigger
        trigger: TimeTrigger | GeoTrigger
        if intent.type == "time":
            trigger = TimeTrigger(due_at=intent.due_at)
        elif intent.type == "geo":
            trigger = GeoTrigger(
                lat=intent.location.lat,
                lon=intent.location.lon,
                radius_m=intent.radius_m,
            )
        else:
            raise ValueError(f"Unsupported intent type: {intent.type}")
        
        # Domain validation
        validate_trigger(trigger, now)
        
        # Create domain entity
        reminder = Reminder(
            id=ReminderId(value=0),  # Will be set by repository
            device_id=device_id,
            text=text,
            trigger=trigger,
            status=ReminderStatus.PENDING,
        )
        
        # Persist via repository
        return self.repository.save(reminder)
