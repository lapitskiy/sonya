"""Evaluate geo triggers use case."""

from datetime import datetime

from ..domain.reminder import Reminder
from ..domain.reminder.value_objects import GeoTrigger
from ..infrastructure.db.repositories import ReminderRepository
from ..infrastructure.geo.geofence import GeofenceService


class EvaluateGeo:
    """Use case: evaluate geo triggers."""
    
    def __init__(
        self,
        repository: ReminderRepository,
        geofence: GeofenceService,
    ):
        self.repository = repository
        self.geofence = geofence
    
    def execute(self, device_id: str, lat: float, lon: float, now: datetime) -> list[Reminder]:
        """Execute use case."""
        # Get active geo reminders
        reminders = self.repository.find_active_geo_by_device(device_id)
        
        # Check which are triggered
        triggered = []
        for reminder in reminders:
            if isinstance(reminder.trigger, GeoTrigger):
                if self.geofence.is_inside(
                    lat, lon,
                    reminder.trigger.lat,
                    reminder.trigger.lon,
                    reminder.trigger.radius_m,
                ):
                    triggered.append(reminder)
        
        return triggered
