"""Core of Daneel.AI: Ollama communication and conversation state."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal

import httpx

from .i18n import DEFAULT_REPLY_LANGUAGE, build_system_prompt

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class Message:
    """A single message in the conversation history."""

    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        """Return the message in the Ollama API format."""
        return {"role": self.role, "content": self.content}


class OllamaError(RuntimeError):
    """An error returned by Ollama or while calling it."""

    message_key: str = "http_error"

    def __init__(self, detail: str = "") -> None:
        self.detail = detail
        super().__init__(detail or self.message_key)


class OllamaConnectionError(OllamaError):
    """Ollama could not be reached."""

    message_key = "connection_error"


class OllamaClient:
    """Asynchronous Ollama client with a streaming response."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        system_prompt: str = build_system_prompt(DEFAULT_REPLY_LANGUAGE),
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt
        self._client = client
        self._timeout = timeout

    async def chat_stream(self, history: Sequence[Message]) -> AsyncIterator[str]:
        """Send the history to /api/chat and yield response chunks as they arrive."""
        payload = {
            "model": self.model,
            "messages": [
                Message("system", self.system_prompt).as_dict(),
                *(message.as_dict() for message in history),
            ],
            "stream": True,
        }

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=5.0)
        )
        try:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise OllamaError(body[:200])

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(chunk, dict) and chunk.get("error"):
                        raise OllamaError(str(chunk["error"]))
                    message = chunk.get("message") if isinstance(chunk, dict) else None
                    content = message.get("content", "") if isinstance(message, dict) else ""
                    if content:
                        yield content
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise OllamaConnectionError(str(exc)) from exc
        finally:
            if owns_client:
                await client.aclose()


class Conversation:
    """A conversation with the agent, including its message history."""

    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()
        self.messages: list[Message] = []

    def clear(self) -> None:
        """Remove all messages from the history."""
        self.messages.clear()

    async def stream_answer(self, user_text: str) -> AsyncIterator[str]:
        """Record the user's message and yield the agent's response chunk by chunk."""
        self.messages.append(Message("user", user_text))
        parts: list[str] = []
        try:
            async for chunk in self.client.chat_stream(self.messages):
                parts.append(chunk)
                yield chunk
        except OllamaError:
            self.messages.pop()
            raise
        self.messages.append(Message("assistant", "".join(parts)))
