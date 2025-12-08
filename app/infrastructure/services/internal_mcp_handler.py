"""
Internal MCP Handler - Handles MCP calls for internal features.

Routes MCP tool calls to internal use cases (tasks, notes, inbox, persons).
These are local features stored in the Claudine database.
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime

from app.application.use_cases.task_use_cases import TaskUseCases
from app.application.use_cases.note_use_cases import NoteUseCases
from app.application.use_cases.inbox_use_cases import InboxUseCases
from app.application.use_cases.person_use_cases import PersonUseCases

logger = logging.getLogger(__name__)


class InternalMCPHandler:
    """
    Handler for internal MCP tool calls.

    Executes tools for internal features:
    - Tasks (create, list, update, complete, delete)
    - Notes (create, list, update, delete)
    - Inbox (list, process, accept, reject)
    - Persons (create, list, update, delete)
    """

    # Tool definitions for discovery
    TASK_TOOLS = [
        {
            "name": "create_task",
            "description": "Maak een nieuwe taak aan. Gebruik dit wanneer de gebruiker vraagt om een taak, todo, opdracht of actie aan te maken.",
            "category": "tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titel of beschrijving van de taak"
                    },
                    "memo": {
                        "type": "string",
                        "description": "Extra notities of details voor de taak"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Deadline in ISO 8601 formaat (YYYY-MM-DD)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Prioriteit van de taak"
                    },
                    "delegated_to_name": {
                        "type": "string",
                        "description": "Naam van de persoon aan wie de taak gedelegeerd wordt"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels/tags voor de taak"
                    }
                },
                "required": ["title"]
            }
        },
        {
            "name": "list_tasks",
            "description": "Toon een lijst van taken. Gebruik dit om openstaande taken, todos of opdrachten te bekijken.",
            "category": "tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["new", "in_progress", "done", "cancelled", "overdue"],
                        "description": "Filter op status"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Filter op prioriteit"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum aantal resultaten",
                        "default": 20
                    }
                }
            }
        },
        {
            "name": "complete_task",
            "description": "Markeer een taak als voltooid. Gebruik dit wanneer een taak afgerond is.",
            "category": "tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "ID van de taak (UUID)"
                    },
                    "task_number": {
                        "type": "integer",
                        "description": "Taaknummer (alternatief voor task_id)"
                    },
                    "annotation": {
                        "type": "string",
                        "description": "Optionele opmerking bij voltooiing"
                    }
                }
            }
        },
        {
            "name": "update_task",
            "description": "Update een bestaande taak. Gebruik dit om taakdetails te wijzigen.",
            "category": "tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "ID van de taak (UUID)"
                    },
                    "task_number": {
                        "type": "integer",
                        "description": "Taaknummer (alternatief voor task_id)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "Nieuwe memo/notities"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Nieuwe deadline (YYYY-MM-DD)"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Nieuwe prioriteit"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["new", "in_progress", "done", "cancelled"],
                        "description": "Nieuwe status"
                    }
                }
            }
        },
        {
            "name": "delete_task",
            "description": "Verwijder een taak. Gebruik dit om een taak permanent te verwijderen.",
            "category": "tasks",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "ID van de taak (UUID)"
                    },
                    "task_number": {
                        "type": "integer",
                        "description": "Taaknummer (alternatief voor task_id)"
                    }
                }
            }
        }
    ]

    NOTE_TOOLS = [
        {
            "name": "create_note",
            "description": "Maak een nieuwe notitie aan. Gebruik dit voor het opslaan van tekst, ideeën of informatie.",
            "category": "notes",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titel van de notitie"
                    },
                    "content": {
                        "type": "string",
                        "description": "Inhoud van de notitie"
                    },
                    "color": {
                        "type": "string",
                        "enum": ["yellow", "blue", "red", "green", "purple", "orange", "pink", "gray", "white"],
                        "description": "Kleur van de notitie"
                    },
                    "is_pinned": {
                        "type": "boolean",
                        "description": "Of de notitie vastgepind moet worden"
                    }
                }
            }
        },
        {
            "name": "list_notes",
            "description": "Toon een lijst van notities. Gebruik dit om opgeslagen notities te bekijken.",
            "category": "notes",
            "input_schema": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Zoekterm in titel en inhoud"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum aantal resultaten",
                        "default": 20
                    }
                }
            }
        },
        {
            "name": "update_note",
            "description": "Update een bestaande notitie.",
            "category": "notes",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "ID van de notitie (UUID)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Nieuwe titel"
                    },
                    "content": {
                        "type": "string",
                        "description": "Nieuwe inhoud"
                    },
                    "color": {
                        "type": "string",
                        "enum": ["yellow", "blue", "red", "green", "purple", "orange", "pink", "gray", "white"],
                        "description": "Nieuwe kleur"
                    }
                },
                "required": ["note_id"]
            }
        },
        {
            "name": "delete_note",
            "description": "Verwijder een notitie.",
            "category": "notes",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "ID van de notitie (UUID)"
                    }
                },
                "required": ["note_id"]
            }
        }
    ]

    PERSON_TOOLS = [
        {
            "name": "create_person",
            "description": "Voeg een nieuw contact toe. Gebruik dit voor het opslaan van contactgegevens.",
            "category": "persons",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Naam van de persoon"
                    },
                    "email": {
                        "type": "string",
                        "description": "E-mailadres"
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "Telefoonnummer"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "list_persons",
            "description": "Toon een lijst van contacten.",
            "category": "persons",
            "input_schema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum aantal resultaten",
                        "default": 50
                    }
                }
            }
        }
    ]

    INBOX_TOOLS = [
        {
            "name": "list_inbox",
            "description": "Toon inbox items die verwerkt moeten worden.",
            "category": "inbox",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["unprocessed", "pending_review", "accepted", "rejected", "archived"],
                        "description": "Filter op status"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum aantal resultaten",
                        "default": 20
                    }
                }
            }
        }
    ]

    def __init__(self, db: Session):
        self.db = db
        self.task_use_cases = TaskUseCases(db)
        self.note_use_cases = NoteUseCases(db)
        self.inbox_use_cases = InboxUseCases(db)
        self.person_use_cases = PersonUseCases(db)

    @classmethod
    def get_all_tools(cls) -> List[Dict[str, Any]]:
        """Get all internal tool definitions."""
        tools = []
        tools.extend([{**t, "provider": "internal_tasks"} for t in cls.TASK_TOOLS])
        tools.extend([{**t, "provider": "internal_notes"} for t in cls.NOTE_TOOLS])
        tools.extend([{**t, "provider": "internal_persons"} for t in cls.PERSON_TOOLS])
        tools.extend([{**t, "provider": "internal_inbox"} for t in cls.INBOX_TOOLS])
        return tools

    @classmethod
    def get_tool_provider(cls, tool_name: str) -> Optional[str]:
        """Determine which internal provider handles a tool."""
        task_tool_names = [t["name"] for t in cls.TASK_TOOLS]
        note_tool_names = [t["name"] for t in cls.NOTE_TOOLS]
        person_tool_names = [t["name"] for t in cls.PERSON_TOOLS]
        inbox_tool_names = [t["name"] for t in cls.INBOX_TOOLS]

        if tool_name in task_tool_names:
            return "internal_tasks"
        elif tool_name in note_tool_names:
            return "internal_notes"
        elif tool_name in person_tool_names:
            return "internal_persons"
        elif tool_name in inbox_tool_names:
            return "internal_inbox"
        return None

    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an internal MCP tool.

        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            user_id: User ID (UUID string)

        Returns:
            Dict with success status and data/error
        """
        try:
            user_uuid = UUID(user_id)

            # Route to appropriate handler
            if tool_name == "create_task":
                return await self._create_task(params, user_uuid)
            elif tool_name == "list_tasks":
                return await self._list_tasks(params, user_uuid)
            elif tool_name == "complete_task":
                return await self._complete_task(params, user_uuid)
            elif tool_name == "update_task":
                return await self._update_task(params, user_uuid)
            elif tool_name == "delete_task":
                return await self._delete_task(params, user_uuid)
            elif tool_name == "create_note":
                return await self._create_note(params, user_uuid)
            elif tool_name == "list_notes":
                return await self._list_notes(params, user_uuid)
            elif tool_name == "update_note":
                return await self._update_note(params, user_uuid)
            elif tool_name == "delete_note":
                return await self._delete_note(params, user_uuid)
            elif tool_name == "create_person":
                return await self._create_person(params, user_uuid)
            elif tool_name == "list_persons":
                return await self._list_persons(params, user_uuid)
            elif tool_name == "list_inbox":
                return await self._list_inbox(params, user_uuid)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Internal MCP execution failed: {e}")
            return {"success": False, "error": str(e)}

    # ==================== Task Handlers ====================

    async def _create_task(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Create a new task."""
        task = self.task_use_cases.create_task(
            user_id=user_id,
            title=params.get("title"),
            memo=params.get("memo"),
            due_date=params.get("due_date"),
            priority=params.get("priority", "medium"),
            delegated_to_name=params.get("delegated_to_name"),
            tags=params.get("tags"),
        )
        return {
            "success": True,
            "data": {
                "task_id": task["id"],
                "task_number": task["task_number"],
                "title": task["title"],
                "status": task["status"],
                "message": f"Taak '{task['title']}' aangemaakt (#{task['task_number']})"
            }
        }

    async def _list_tasks(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """List tasks with optional filters."""
        tasks = self.task_use_cases.list_tasks(
            user_id=user_id,
            status=params.get("status"),
            priority=params.get("priority"),
            limit=params.get("limit", 20),
        )
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "count": len(tasks),
                "message": f"{len(tasks)} taken gevonden"
            }
        }

    async def _complete_task(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Mark a task as completed."""
        task_id = params.get("task_id")
        task_number = params.get("task_number")

        if task_number and not task_id:
            # Look up task by number
            task = self.task_use_cases.get_task_by_number(task_number, user_id)
            if not task:
                return {"success": False, "error": f"Taak #{task_number} niet gevonden"}
            task_id = task["id"]

        if not task_id:
            return {"success": False, "error": "task_id of task_number is vereist"}

        task = self.task_use_cases.update_task_status(
            task_id=UUID(task_id),
            user_id=user_id,
            new_status="done",
            annotation=params.get("annotation"),
        )

        if not task:
            return {"success": False, "error": "Taak niet gevonden"}

        return {
            "success": True,
            "data": {
                "task_id": task["id"],
                "title": task["title"],
                "status": "done",
                "message": f"Taak '{task['title']}' voltooid"
            }
        }

    async def _update_task(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Update a task."""
        task_id = params.get("task_id")
        task_number = params.get("task_number")

        if task_number and not task_id:
            task = self.task_use_cases.get_task_by_number(task_number, user_id)
            if not task:
                return {"success": False, "error": f"Taak #{task_number} niet gevonden"}
            task_id = task["id"]

        if not task_id:
            return {"success": False, "error": "task_id of task_number is vereist"}

        # Update status if provided
        if "status" in params:
            task = self.task_use_cases.update_task_status(
                task_id=UUID(task_id),
                user_id=user_id,
                new_status=params["status"],
            )

        # Update other fields
        task = self.task_use_cases.update_task_fields(
            task_id=UUID(task_id),
            user_id=user_id,
            memo=params.get("memo"),
            due_date=params.get("due_date"),
            tags=params.get("tags"),
        )

        if not task:
            return {"success": False, "error": "Taak niet gevonden"}

        return {
            "success": True,
            "data": {
                "task_id": task["id"],
                "title": task["title"],
                "message": f"Taak '{task['title']}' bijgewerkt"
            }
        }

    async def _delete_task(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Delete a task."""
        task_id = params.get("task_id")
        task_number = params.get("task_number")

        if task_number and not task_id:
            task = self.task_use_cases.get_task_by_number(task_number, user_id)
            if not task:
                return {"success": False, "error": f"Taak #{task_number} niet gevonden"}
            task_id = task["id"]

        if not task_id:
            return {"success": False, "error": "task_id of task_number is vereist"}

        deleted = self.task_use_cases.delete_task(UUID(task_id), user_id)

        if not deleted:
            return {"success": False, "error": "Taak niet gevonden"}

        return {
            "success": True,
            "data": {"message": "Taak verwijderd"}
        }

    # ==================== Note Handlers ====================

    async def _create_note(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Create a new note."""
        note = self.note_use_cases.create_note(
            user_id=user_id,
            title=params.get("title"),
            content=params.get("content"),
            color=params.get("color", "yellow"),
            is_pinned=params.get("is_pinned", False),
        )
        return {
            "success": True,
            "data": {
                "note_id": note["id"],
                "title": note.get("title"),
                "message": f"Notitie aangemaakt"
            }
        }

    async def _list_notes(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """List notes."""
        notes = self.note_use_cases.list_notes(
            user_id=user_id,
            search=params.get("search"),
            limit=params.get("limit", 20),
        )
        return {
            "success": True,
            "data": {
                "notes": notes,
                "count": len(notes),
                "message": f"{len(notes)} notities gevonden"
            }
        }

    async def _update_note(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Update a note."""
        note_id = params.get("note_id")
        if not note_id:
            return {"success": False, "error": "note_id is vereist"}

        note = self.note_use_cases.update_note(
            note_id=UUID(note_id),
            user_id=user_id,
            title=params.get("title"),
            content=params.get("content"),
            color=params.get("color"),
        )

        if not note:
            return {"success": False, "error": "Notitie niet gevonden"}

        return {
            "success": True,
            "data": {
                "note_id": note["id"],
                "message": "Notitie bijgewerkt"
            }
        }

    async def _delete_note(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Delete a note."""
        note_id = params.get("note_id")
        if not note_id:
            return {"success": False, "error": "note_id is vereist"}

        deleted = self.note_use_cases.delete_note(
            note_id=UUID(note_id),
            user_id=user_id,
            soft_delete=False,
        )

        if not deleted:
            return {"success": False, "error": "Notitie niet gevonden"}

        return {
            "success": True,
            "data": {"message": "Notitie verwijderd"}
        }

    # ==================== Person Handlers ====================

    async def _create_person(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Create a new person/contact."""
        person = self.person_use_cases.create_person(
            user_id=user_id,
            name=params.get("name"),
            email=params.get("email"),
            phone_number=params.get("phone_number"),
        )
        return {
            "success": True,
            "data": {
                "person_id": person["id"],
                "name": person["name"],
                "message": f"Contact '{person['name']}' aangemaakt"
            }
        }

    async def _list_persons(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """List persons/contacts."""
        persons = self.person_use_cases.list_persons(
            user_id=user_id,
            limit=params.get("limit", 50),
        )
        return {
            "success": True,
            "data": {
                "persons": persons,
                "count": len(persons),
                "message": f"{len(persons)} contacten gevonden"
            }
        }

    # ==================== Inbox Handlers ====================

    async def _list_inbox(self, params: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """List inbox items."""
        result = self.inbox_use_cases.get_inbox_items(
            user_id=user_id,
            status=params.get("status"),
            limit=params.get("limit", 20),
        )
        return {
            "success": True,
            "data": {
                "items": result.get("items", []),
                "count": result.get("total", 0),
                "message": f"{result.get('total', 0)} inbox items"
            }
        }
