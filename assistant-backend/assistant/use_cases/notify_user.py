"""Notify user use case."""

from datetime import datetime

from ..domain.reminder import Reminder
from ..infrastructure.notifications.push_gateway import PushGateway


class NotifyUser:
    """Use case: notify user about reminder."""
    
    def __init__(self, push_gateway: PushGateway):
        self.push_gateway = push_gateway
    
    def execute(self, reminder: Reminder, now: datetime) -> None:
        """Execute use case."""
        self.push_gateway.send(
            device_id=reminder.device_id,
            title="Reminder",
            body=reminder.text,
        )
