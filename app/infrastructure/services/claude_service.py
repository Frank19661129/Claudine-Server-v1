"""
Claude AI service - Anthropic API integration.
Part of Infrastructure layer.
"""
import httpx
import json
from typing import List, Dict, Optional, AsyncIterator, Any
from app.core.config import settings


class ClaudeService:
    """
    Claude AI conversation service using Anthropic API.
    Provides chat completions with streaming support.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-3-haiku-20240307"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def get_calendar_tools(self) -> List[Dict[str, Any]]:
        """
        Define calendar tools for Anthropic Tool Use.
        Claude can call these tools to create calendar events and reminders.
        """
        return [
            {
                "name": "create_calendar_event",
                "description": "Maak een nieuwe afspraak in de agenda van de gebruiker. Gebruik dit wanneer de gebruiker vraagt om een afspraak, meeting, evenement of activiteit in te plannen.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Titel van de afspraak (bijv. 'Lunch met vis', 'Vergadering met team')"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Starttijd in ISO 8601 formaat (bijv. '2025-11-16T12:00:00'). Gebruik de huidige datum/tijd als referentie voor relatieve tijden."
                        },
                        "end_time": {
                            "type": "string",
                            "description": "Eindtijd in ISO 8601 formaat (bijv. '2025-11-16T13:00:00')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Optionele beschrijving van de afspraak"
                        },
                        "location": {
                            "type": "string",
                            "description": "Optionele locatie van de afspraak"
                        },
                        "provider": {
                            "type": "string",
                            "description": "VERPLICHT als de gebruiker een specifieke kalender noemt! 'google' als gebruiker zegt: google, gcal, google calendar, google agenda. 'microsoft' als gebruiker zegt: microsoft, outlook, o365, office 365, office agenda. LAAT LEEG als gebruiker geen provider noemt.",
                            "enum": ["google", "microsoft"]
                        }
                    },
                    "required": ["title", "start_time", "end_time"]
                }
            },
            {
                "name": "create_reminder",
                "description": "Maak een herinnering voor de gebruiker. Gebruik dit voor taken of acties die op een specifiek moment moeten gebeuren. Herinneringen zijn 5 minuten lang.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Titel van de herinnering (zonder emoji - die wordt automatisch toegevoegd)"
                        },
                        "reminder_time": {
                            "type": "string",
                            "description": "Tijdstip van de herinnering in ISO 8601 formaat (bijv. '2025-11-16T18:00:00')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Optionele beschrijving"
                        },
                        "provider": {
                            "type": "string",
                            "description": "VERPLICHT als de gebruiker een specifieke kalender noemt! 'google' als gebruiker zegt: google, gcal, google calendar, google agenda. 'microsoft' als gebruiker zegt: microsoft, outlook, o365, office 365, office agenda. LAAT LEEG als gebruiker geen provider noemt.",
                            "enum": ["google", "microsoft"]
                        }
                    },
                    "required": ["title", "reminder_time"]
                }
            }
        ]

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
    ) -> Dict:
        """
        Send a message to Claude and get response.

        Args:
            messages: List of messages [{"role": "user", "content": "..."}]
            system_prompt: Optional system prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)

        Returns:
            Response dict with content, stop_reason, usage, etc.

        Raises:
            Exception: If API call fails
        """
        body = {
            "model": model or self.DEFAULT_MODEL,
            "max_tokens": max_tokens or self.DEFAULT_MAX_TOKENS,
            "messages": messages,
            "temperature": temperature,
        }

        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.API_URL,
                headers=self.headers,
                json=body,
            )

            if response.status_code != 200:
                error_detail = response.text
                raise Exception(f"Claude API error ({response.status_code}): {error_detail}")

            data = response.json()
            return data

    async def send_message_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Send a message to Claude and stream response.

        Args:
            messages: List of messages [{"role": "user", "content": "..."}]
            system_prompt: Optional system prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            tools: Optional list of tools for function calling

        Yields:
            Dict with event type and data (text chunks or tool use)

        Raises:
            Exception: If API call fails
        """
        body = {
            "model": model or self.DEFAULT_MODEL,
            "max_tokens": max_tokens or self.DEFAULT_MAX_TOKENS,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if system_prompt:
            body["system"] = system_prompt

        if tools:
            body["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self.API_URL,
                headers=self.headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_detail = await response.aread()
                    raise Exception(f"Claude API error ({response.status_code}): {error_detail.decode()}")

                # Parse SSE stream
                current_tool_use = None

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # Skip comments and empty lines
                    if line.startswith(":") or not line.strip():
                        continue

                    # Parse SSE format: "event: xxx" and "data: xxx"
                    if line.startswith("event:"):
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()

                        # Skip ping events
                        if data_str == "[DONE]":
                            break

                        try:
                            event_data = json.loads(data_str)

                            # Handle different event types
                            event_type = event_data.get("type")

                            if event_type == "content_block_start":
                                # Start of a new content block
                                content_block = event_data.get("content_block", {})
                                if content_block.get("type") == "tool_use":
                                    # Start collecting tool use data
                                    current_tool_use = {
                                        "id": content_block.get("id"),
                                        "name": content_block.get("name"),
                                        "input": ""
                                    }

                            elif event_type == "content_block_delta":
                                delta = event_data.get("delta", {})

                                if delta.get("type") == "text_delta":
                                    # Regular text response
                                    text = delta.get("text", "")
                                    if text:
                                        yield {"type": "text", "text": text}

                                elif delta.get("type") == "input_json_delta":
                                    # Tool input being streamed
                                    if current_tool_use:
                                        current_tool_use["input"] += delta.get("partial_json", "")

                            elif event_type == "content_block_stop":
                                # End of content block
                                if current_tool_use:
                                    # Parse complete tool input
                                    try:
                                        current_tool_use["input"] = json.loads(current_tool_use["input"])
                                    except json.JSONDecodeError:
                                        pass

                                    # Yield complete tool use
                                    yield {
                                        "type": "tool_use",
                                        "id": current_tool_use["id"],
                                        "name": current_tool_use["name"],
                                        "input": current_tool_use["input"]
                                    }
                                    current_tool_use = None

                            elif event_type == "message_stop":
                                break

                        except json.JSONDecodeError:
                            # Skip malformed JSON
                            continue

    def get_system_prompt(self, mode: str = "chat") -> str:
        """
        Get system prompt based on conversation mode.

        Args:
            mode: Conversation mode (chat, voice, note, scan)

        Returns:
            System prompt string
        """
        prompts = {
            "chat": """Je bent PAI, een slimme Nederlandse persoonlijke assistent.

Je helpt met:
- Agenda beheer via Google/Microsoft Calendar
- Notities maken en organiseren
- Documenten scannen en verwerken
- Algemene vragen beantwoorden

KRITIEKE REGELS VOOR ACTIES:
- Als de gebruiker een afspraak, meeting, evenement of herinnering wil maken: VERPLICHT gebruik de 'create_calendar_event' of 'create_reminder' tool
- NOOIT een fake success message geven zonder daadwerkelijk een tool uit te voeren
- Als je niet 100% zeker weet wat de gebruiker bedoelt: VRAAG OM VERDUIDELIJKING, voer GEEN actie uit
- Als datums/tijden onduidelijk zijn: VRAAG SPECIFIEK naar datum en tijd voordat je de tool gebruikt
- Gebruik de tools ALTIJD voor agenda-gerelateerde acties, ongeacht of de gebruiker een # commando gebruikt of niet

Andere regels:
- Antwoord altijd in het Nederlands tenzij gevraagd anders
- Wees vriendelijk, behulpzaam en to-the-point
- Als iets onduidelijk is, stel dan verduidelijkende vragen

Beschikbare commando's (optioneel):
- #calendar - Voor afspraken en agenda
- #note - Voor notities maken
- #scan - Voor documenten scannen
""",
            "voice": """Je bent PAI, een slimme Nederlandse spraakassistent.

Optimaliseer antwoorden voor spraak:
- Korte, duidelijke zinnen
- Geen opsommingen met bullets
- Gebruik natuurlijke taal
- Vraag om bevestiging bij belangrijke acties

Je helpt met agenda, notities, documenten en algemene vragen.
""",
            "note": """Je bent PAI in notitie-modus.

Help gebruikers met:
- Notities structureren en organiseren
- Belangrijke punten samenvatten
- Tags en categorieën voorstellen
- Actiepunten identificeren
""",
            "scan": """Je bent PAI in scan-modus.

Help gebruikers met:
- Documenten analyseren
- Tekst extraheren en structureren
- Belangrijke informatie identificeren
- Samenvatten van gescande content
""",
        }

        return prompts.get(mode, prompts["chat"])
