"""
Command parser service - keyword routing for chat commands.
Part of Domain layer - business logic for command detection and routing.
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """Available command types."""
    CALENDAR = "calendar"
    NOTE = "note"
    SCAN = "scan"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """
    Parsed command result.
    """
    command_type: CommandType
    original_text: str
    command_text: str  # Text after the command keyword
    parameters: Dict[str, Any]  # Extracted parameters

    def is_command(self) -> bool:
        """Check if this is a valid command (not unknown)."""
        return self.command_type != CommandType.UNKNOWN

    def get_help_text(self) -> str:
        """Get help text for the command."""
        help_texts = {
            CommandType.CALENDAR: """📅 Calendar commando's:

#calendar afspraak maken - Maak nieuwe afspraak
#calendar lijst - Toon komende afspraken
#calendar vandaag - Afspraken vandaag
#calendar morgen - Afspraken morgen

Voorbeelden:
- #calendar afspraak maken om 14:00 met Jan
- #calendar lijst deze week
- #calendar verwijder afspraak <id>
""",
            CommandType.NOTE: """📝 Notitie commando's:

#note maken - Nieuwe notitie
#note lijst - Toon notities
#note zoek <term> - Zoek in notities

Voorbeelden:
- #note maken: boodschappen melk brood eieren
- #note lijst vandaag
- #note zoek vergadering
""",
            CommandType.SCAN: """📸 Scan commando's:

#scan document - Scan en verwerk document
#scan foto - Scan foto/afbeelding
#scan bon - Scan kassabon

Voorbeelden:
- #scan document contract.pdf
- #scan bon voor declaratie
""",
            CommandType.HELP: """❓ Beschikbare commando's:

📅 #calendar - Agenda beheer
📝 #note - Notities maken
📸 #scan - Documenten scannen
❓ #help - Deze help tekst

Gebruik #help <commando> voor meer info over een specifiek commando.
Bijvoorbeeld: #help calendar
""",
        }

        return help_texts.get(self.command_type, "Onbekend commando. Typ #help voor beschikbare commando's.")


class CommandParser:
    """
    Service for parsing chat commands with keywords.
    Detects commands like #calendar, #note, #scan and extracts parameters.
    """

    COMMAND_PREFIX = "#"
    COMMAND_KEYWORDS = {
        "calendar": CommandType.CALENDAR,
        "agenda": CommandType.CALENDAR,
        "cal": CommandType.CALENDAR,
        "note": CommandType.NOTE,
        "notitie": CommandType.NOTE,
        "scan": CommandType.SCAN,
        "help": CommandType.HELP,
        "hulp": CommandType.HELP,
    }

    @classmethod
    def parse(cls, text: str) -> ParsedCommand:
        """
        Parse text for commands.

        Args:
            text: User input text

        Returns:
            ParsedCommand with detected command and parameters
        """
        text = text.strip()

        # Check if text starts with command prefix
        if not text.startswith(cls.COMMAND_PREFIX):
            return ParsedCommand(
                command_type=CommandType.UNKNOWN,
                original_text=text,
                command_text="",
                parameters={},
            )

        # Extract first word (the command)
        parts = text.split(maxsplit=1)
        command_word = parts[0][1:].lower()  # Remove # and lowercase
        command_text = parts[1] if len(parts) > 1 else ""

        # Map to command type
        command_type = cls.COMMAND_KEYWORDS.get(command_word, CommandType.UNKNOWN)

        # Extract parameters based on command type
        parameters = cls._extract_parameters(command_type, command_text)

        return ParsedCommand(
            command_type=command_type,
            original_text=text,
            command_text=command_text,
            parameters=parameters,
        )

    @classmethod
    def _extract_parameters(cls, command_type: CommandType, text: str) -> Dict[str, Any]:
        """
        Extract parameters from command text.

        Args:
            command_type: Type of command
            text: Text after command keyword

        Returns:
            Dict with extracted parameters
        """
        params = {"raw_text": text}

        if command_type == CommandType.CALENDAR:
            params.update(cls._extract_calendar_params(text))
        elif command_type == CommandType.NOTE:
            params.update(cls._extract_note_params(text))
        elif command_type == CommandType.SCAN:
            params.update(cls._extract_scan_params(text))
        elif command_type == CommandType.HELP:
            params.update(cls._extract_help_params(text))

        return params

    @classmethod
    def _extract_calendar_params(cls, text: str) -> Dict[str, Any]:
        """Extract calendar-specific parameters."""
        text_lower = text.lower()

        # Detect action
        action = "unknown"
        if any(word in text_lower for word in ["maak", "plan", "afspraak", "toevoeg"]):
            action = "create"
        elif any(word in text_lower for word in ["lijst", "toon", "bekijk", "overzicht"]):
            action = "list"
        elif any(word in text_lower for word in ["vandaag", "today"]):
            action = "today"
        elif any(word in text_lower for word in ["morgen", "tomorrow"]):
            action = "tomorrow"
        elif any(word in text_lower for word in ["verwijder", "delete", "annuleer"]):
            action = "delete"

        return {
            "action": action,
            "time_context": cls._extract_time_context(text_lower),
        }

    @classmethod
    def _extract_note_params(cls, text: str) -> Dict[str, Any]:
        """Extract note-specific parameters."""
        text_lower = text.lower()

        action = "unknown"
        if any(word in text_lower for word in ["maak", "nieuw", "schrijf"]):
            action = "create"
        elif any(word in text_lower for word in ["lijst", "toon", "bekijk"]):
            action = "list"
        elif any(word in text_lower for word in ["zoek", "vind", "search"]):
            action = "search"

        return {"action": action}

    @classmethod
    def _extract_scan_params(cls, text: str) -> Dict[str, Any]:
        """Extract scan-specific parameters."""
        text_lower = text.lower()

        scan_type = "document"
        if "bon" in text_lower or "receipt" in text_lower:
            scan_type = "receipt"
        elif "foto" in text_lower or "image" in text_lower:
            scan_type = "image"
        elif "document" in text_lower or "pdf" in text_lower:
            scan_type = "document"

        return {"scan_type": scan_type}

    @classmethod
    def _extract_help_params(cls, text: str) -> Dict[str, Any]:
        """Extract help-specific parameters."""
        text_lower = text.lower()

        topic = None
        for keyword, cmd_type in cls.COMMAND_KEYWORDS.items():
            if keyword in text_lower:
                topic = cmd_type
                break

        return {"topic": topic}

    @classmethod
    def _extract_time_context(cls, text: str) -> Optional[str]:
        """Extract time context from text."""
        if any(word in text for word in ["vandaag", "today"]):
            return "today"
        elif any(word in text for word in ["morgen", "tomorrow"]):
            return "tomorrow"
        elif any(word in text for word in ["week", "deze week"]):
            return "this_week"
        elif any(word in text for word in ["maand", "deze maand"]):
            return "this_month"

        return None

    @classmethod
    def is_command(cls, text: str) -> bool:
        """
        Quick check if text contains a command.

        Args:
            text: User input text

        Returns:
            True if text starts with command prefix
        """
        return text.strip().startswith(cls.COMMAND_PREFIX)
