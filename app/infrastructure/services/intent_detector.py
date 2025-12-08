"""
Intent Detector - Unified intent detection for commands and chat.

Detects:
- Command-based intents (#calendar, #task, #note, etc.)
- Chat-based intents (natural language about appointments, tasks, etc.)
- Provider mentions (google, microsoft, outlook, etc.)
- Date/time references
"""
import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of detected intents"""
    CALENDAR_CREATE = "calendar:create"
    CALENDAR_LIST = "calendar:list"
    CALENDAR_REMINDER = "calendar:reminder"
    CALENDAR_UPDATE = "calendar:update"
    CALENDAR_DELETE = "calendar:delete"
    TASK_CREATE = "task:create"
    TASK_LIST = "task:list"
    NOTE_CREATE = "note:create"
    UNKNOWN = "unknown"


@dataclass
class DetectedIntent:
    """Result of intent detection"""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    source: str  # "command" or "chat"
    provider: Optional[str]  # "google", "microsoft", or None
    raw_input: str
    extracted_params: Dict[str, Any]
    needs_claude_extraction: bool  # True if Claude should extract details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "source": self.source,
            "provider": self.provider,
            "raw_input": self.raw_input,
            "extracted_params": self.extracted_params,
            "needs_claude_extraction": self.needs_claude_extraction,
        }


class IntentDetector:
    """
    Unified intent detection for all input types.

    Works with:
    - Commands: #calendar lunch morgen 12:00
    - Chat: "plan een meeting met Jan volgende week"
    - Voice: same as chat
    """

    # Command patterns
    COMMAND_PATTERNS = {
        "#calendar": IntentType.CALENDAR_CREATE,
        "#afspraak": IntentType.CALENDAR_CREATE,
        "#agenda": IntentType.CALENDAR_LIST,
        "#reminder": IntentType.CALENDAR_REMINDER,
        "#herinner": IntentType.CALENDAR_REMINDER,
        "#task": IntentType.TASK_CREATE,
        "#taak": IntentType.TASK_CREATE,
        "#note": IntentType.NOTE_CREATE,
        "#notitie": IntentType.NOTE_CREATE,
    }

    # Provider detection patterns
    PROVIDER_PATTERNS = {
        "google": ["google", "gcal", "google calendar", "google agenda"],
        "microsoft": ["microsoft", "outlook", "o365", "office 365", "office", "office agenda"],
    }

    # Calendar intent keywords (Dutch + English)
    CALENDAR_KEYWORDS = [
        "afspraak", "meeting", "vergadering", "lunch", "diner", "ontbijt",
        "appointment", "event", "agenda", "calendar", "plannen", "inplannen",
        "schedule", "plan", "boek", "reserveer", "book",
    ]

    REMINDER_KEYWORDS = [
        "herinner", "remind", "reminder", "herinnering", "onthoud",
        "vergeet niet", "don't forget", "alert",
    ]

    # Days of week (Dutch)
    DAYS_NL = {
        "maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3,
        "vrijdag": 4, "zaterdag": 5, "zondag": 6,
    }

    def __init__(self):
        self.tz = ZoneInfo("Europe/Amsterdam")

    def detect(self, user_input: str) -> DetectedIntent:
        """
        Detect intent from user input.

        Args:
            user_input: Raw user input (command or chat)

        Returns:
            DetectedIntent with type, confidence, and extracted info
        """
        input_lower = user_input.lower().strip()

        # Check for command first
        if input_lower.startswith("#"):
            return self._detect_command_intent(user_input)

        # Otherwise, detect from natural language
        return self._detect_chat_intent(user_input)

    def _detect_command_intent(self, user_input: str) -> DetectedIntent:
        """Detect intent from # command."""
        input_lower = user_input.lower().strip()

        # Find matching command
        intent_type = IntentType.UNKNOWN
        command_found = None

        for command, itype in self.COMMAND_PATTERNS.items():
            if input_lower.startswith(command):
                intent_type = itype
                command_found = command
                break

        if intent_type == IntentType.UNKNOWN:
            return DetectedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                source="command",
                provider=None,
                raw_input=user_input,
                extracted_params={},
                needs_claude_extraction=False,
            )

        # Extract rest of input after command
        rest = user_input[len(command_found):].strip()

        # Detect provider
        provider = self._detect_provider(rest)

        # Extract basic params
        extracted_params = self._extract_basic_params(rest)

        return DetectedIntent(
            intent_type=intent_type,
            confidence=1.0,  # Commands are explicit
            source="command",
            provider=provider,
            raw_input=user_input,
            extracted_params=extracted_params,
            needs_claude_extraction=True,  # Claude should parse date/time/title
        )

    def _detect_chat_intent(self, user_input: str) -> DetectedIntent:
        """Detect intent from natural language chat."""
        input_lower = user_input.lower()

        # Detect provider
        provider = self._detect_provider(user_input)

        # Check for reminder keywords first (more specific)
        if any(kw in input_lower for kw in self.REMINDER_KEYWORDS):
            return DetectedIntent(
                intent_type=IntentType.CALENDAR_REMINDER,
                confidence=0.8,
                source="chat",
                provider=provider,
                raw_input=user_input,
                extracted_params={},
                needs_claude_extraction=True,
            )

        # Check for calendar keywords
        if any(kw in input_lower for kw in self.CALENDAR_KEYWORDS):
            # Determine if list or create
            if any(word in input_lower for word in ["wat", "welke", "toon", "show", "list", "bekijk"]):
                intent_type = IntentType.CALENDAR_LIST
            else:
                intent_type = IntentType.CALENDAR_CREATE

            return DetectedIntent(
                intent_type=intent_type,
                confidence=0.7,
                source="chat",
                provider=provider,
                raw_input=user_input,
                extracted_params={},
                needs_claude_extraction=True,
            )

        # No clear intent detected
        return DetectedIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            source="chat",
            provider=provider,
            raw_input=user_input,
            extracted_params={},
            needs_claude_extraction=False,
        )

    def _detect_provider(self, text: str) -> Optional[str]:
        """Detect if user mentions a specific provider."""
        text_lower = text.lower()

        for provider, patterns in self.PROVIDER_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    logger.debug(f"Detected provider '{provider}' from pattern '{pattern}'")
                    return provider

        return None

    def _extract_basic_params(self, text: str) -> Dict[str, Any]:
        """Extract basic parameters from text without Claude."""
        params = {}

        # Try to detect date references
        text_lower = text.lower()

        now = datetime.now(self.tz)

        # Check for "morgen"
        if "morgen" in text_lower:
            params["date_hint"] = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            params["date_type"] = "morgen"

        # Check for "overmorgen"
        elif "overmorgen" in text_lower:
            params["date_hint"] = (now + timedelta(days=2)).strftime("%Y-%m-%d")
            params["date_type"] = "overmorgen"

        # Check for "vandaag"
        elif "vandaag" in text_lower:
            params["date_hint"] = now.strftime("%Y-%m-%d")
            params["date_type"] = "vandaag"

        # Check for weekday names
        else:
            for day_name, day_num in self.DAYS_NL.items():
                if day_name in text_lower:
                    # Calculate next occurrence of this weekday
                    days_ahead = day_num - now.weekday()
                    if days_ahead <= 0:  # Target day already happened this week
                        days_ahead += 7
                    target_date = now + timedelta(days=days_ahead)
                    params["date_hint"] = target_date.strftime("%Y-%m-%d")
                    params["date_type"] = day_name
                    break

        # Try to extract time (HH:MM or HH.MM or HHu or HH uur)
        time_patterns = [
            r'(\d{1,2})[:\.](\d{2})',  # 12:00 or 12.00
            r'(\d{1,2})\s*(?:u|uur)',  # 12u or 12 uur
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                if len(match.groups()) == 2:
                    params["time_hint"] = f"{int(match.group(1)):02d}:{match.group(2)}"
                else:
                    params["time_hint"] = f"{int(match.group(1)):02d}:00"
                break

        return params

    def get_date_context(self) -> Dict[str, Any]:
        """
        Get current date context for Claude prompts.

        Returns formatted date information for accurate date parsing.
        """
        now = datetime.now(self.tz)

        days_nl = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']

        # Build week view
        week_info = []
        for i in range(7):
            day = now + timedelta(days=i)
            day_name = days_nl[day.weekday()]
            label = "VANDAAG" if i == 0 else "MORGEN" if i == 1 else ""
            week_info.append({
                "day": day_name,
                "date": day.strftime("%d-%m-%Y"),
                "iso": day.strftime("%Y-%m-%d"),
                "label": label,
            })

        return {
            "now": now.isoformat(),
            "today": now.strftime("%Y-%m-%d"),
            "today_name": days_nl[now.weekday()],
            "week": week_info,
            "timezone": "Europe/Amsterdam",
        }
