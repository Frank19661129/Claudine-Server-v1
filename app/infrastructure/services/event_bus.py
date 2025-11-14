"""
Event Bus for command processing.
Part of Infrastructure layer.

This is a simple in-memory event bus for v1 foundation.
In production, this should be replaced with a persistent queue (Redis, RabbitMQ, etc.)
"""
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4, UUID
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Domain event with metadata."""

    id: UUID
    name: str
    payload: Dict[str, Any]
    timestamp: datetime
    user_id: Optional[UUID] = None

    @classmethod
    def create(cls, name: str, payload: Dict[str, Any], user_id: Optional[UUID] = None) -> "Event":
        """Create a new event."""
        return cls(
            id=uuid4(),
            name=name,
            payload=payload,
            timestamp=datetime.utcnow(),
            user_id=user_id,
        )


class EventBus:
    """
    Simple in-memory event bus for command processing.

    Features:
    - Publish/Subscribe pattern
    - Async event handlers
    - Multiple subscribers per event type
    - Error handling with logging

    Future enhancements:
    - Persistent queue (Redis/RabbitMQ)
    - Retry logic
    - Dead letter queue
    - Event history/audit
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []

    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_name: Name of the event to subscribe to
            handler: Async function to handle the event
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        self._subscribers[event_name].append(handler)
        logger.info(f"Subscribed handler {handler.__name__} to event {event_name}")

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        logger.info(f"Publishing event: {event.name} (ID: {event.id})")

        # Store in history (limited to last 1000 events)
        self._event_history.append(event)
        if len(self._event_history) > 1000:
            self._event_history.pop(0)

        # Get subscribers for this event type
        handlers = self._subscribers.get(event.name, [])

        if not handlers:
            logger.warning(f"No subscribers for event: {event.name}")
            return

        # Execute all handlers concurrently
        tasks = []
        for handler in handlers:
            tasks.append(self._execute_handler(handler, event))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Callable, event: Event) -> None:
        """
        Execute a single event handler with error handling.

        Args:
            handler: Event handler function
            event: Event to process
        """
        try:
            logger.debug(f"Executing handler {handler.__name__} for event {event.name}")
            await handler(event)
            logger.debug(f"Handler {handler.__name__} completed successfully")
        except Exception as e:
            logger.error(
                f"Error in handler {handler.__name__} for event {event.name}: {str(e)}",
                exc_info=True,
            )

    def get_event_history(self, limit: int = 100) -> List[Event]:
        """
        Get recent event history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent events
        """
        return self._event_history[-limit:]


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
