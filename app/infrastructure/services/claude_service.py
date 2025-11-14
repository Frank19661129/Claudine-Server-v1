"""
Claude AI service - Anthropic API integration.
Part of Infrastructure layer.
"""
import httpx
from typing import List, Dict, Optional, AsyncIterator
from app.core.config import settings


class ClaudeService:
    """
    Claude AI conversation service using Anthropic API.
    Provides chat completions with streaming support.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
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
    ) -> AsyncIterator[str]:
        """
        Send a message to Claude and stream response.

        Args:
            messages: List of messages [{"role": "user", "content": "..."}]
            system_prompt: Optional system prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive

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
                            import json
                            event_data = json.loads(data_str)

                            # Handle different event types
                            event_type = event_data.get("type")

                            if event_type == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        yield text

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
            "chat": """Je bent Claudine, een slimme Nederlandse persoonlijke assistent.

Je helpt met:
- Agenda beheer via Google/Microsoft Calendar
- Notities maken en organiseren
- Documenten scannen en verwerken
- Algemene vragen beantwoorden

Belangrijke regels:
- Antwoord altijd in het Nederlands tenzij gevraagd anders
- Wees vriendelijk, behulpzaam en to-the-point
- Als gebruiker een commando gebruikt (#calendar, #note, #scan), geef dan duidelijke instructies
- Stel verduidelijkende vragen als iets onduidelijk is

Beschikbare commando's:
- #calendar - Voor afspraken en agenda
- #note - Voor notities maken
- #scan - Voor documenten scannen
""",
            "voice": """Je bent Claudine, een slimme Nederlandse spraakassistent.

Optimaliseer antwoorden voor spraak:
- Korte, duidelijke zinnen
- Geen opsommingen met bullets
- Gebruik natuurlijke taal
- Vraag om bevestiging bij belangrijke acties

Je helpt met agenda, notities, documenten en algemene vragen.
""",
            "note": """Je bent Claudine in notitie-modus.

Help gebruikers met:
- Notities structureren en organiseren
- Belangrijke punten samenvatten
- Tags en categorieën voorstellen
- Actiepunten identificeren
""",
            "scan": """Je bent Claudine in scan-modus.

Help gebruikers met:
- Documenten analyseren
- Tekst extraheren en structureren
- Belangrijke informatie identificeren
- Samenvatten van gescande content
""",
        }

        return prompts.get(mode, prompts["chat"])
