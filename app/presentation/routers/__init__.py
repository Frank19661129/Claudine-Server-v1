"""
Presentation layer routers.
"""
from app.presentation.routers import (
    health,
    auth,
    calendar,
    conversation,
    monitor,
    persons,
    tasks,
    notes,
    inbox,
    mcp,
)

__all__ = [
    "health",
    "auth",
    "calendar",
    "conversation",
    "monitor",
    "persons",
    "tasks",
    "notes",
    "inbox",
    "mcp",
]
