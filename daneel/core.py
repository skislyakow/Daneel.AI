"""Core of Daneel.AI: Ollama communication and conversation state."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from . import config
from .config import Settings
from .i18n import DEFAULT_REPLY_LANGUAGE, build_system_prompt
from .tools import Confirm, ToolError, ToolRegistry

MAX_TOOL_ROUNDS = 5

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class Message:
    """A single message in the conversation history."""

    role: Role
    content: str
    tool_calls: list[dict[str, Any]] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the message in the Ollama API format."""
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        return data


@dataclass(slots=True)
class TextChunk:
    """A piece of the assistant's text response."""

    text: str


@dataclass(slots=True)
class ToolCalls:
    """Tool calls requested by the assistant."""

    calls: list[dict[str, Any]]


@dataclass(slots=True)
class ToolResultEvent:
    """Result of an executed tool call."""

    name: str
    result: str


StreamEvent = TextChunk | ToolCalls | ToolResultEvent


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
        base_url: str | None = None,
        model: str | None = None,
        system_prompt: str = build_system_prompt(DEFAULT_REPLY_LANGUAGE),
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = (
            config.DEFAULT_BASE_URL if base_url is None else base_url
        ).rstrip("/")
        self.model = config.DEFAULT_MODEL if model is None else model
        self.system_prompt = system_prompt
        self.tools = list(tools or [])
        self._client = client
        self._timeout = timeout

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        system_prompt: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> OllamaClient:
        """Build a client from runtime settings."""
        return cls(
            base_url=settings.base_url,
            model=settings.model,
            system_prompt=system_prompt or build_system_prompt(settings.reply_language),
            client=client,
            timeout=timeout,
            tools=tools,
        )

    async def chat_stream(self, history: Sequence[Message]) -> AsyncIterator[StreamEvent]:
        """Send the history to /api/chat and yield text chunks and tool calls."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                Message("system", self.system_prompt).as_dict(),
                *(message.as_dict() for message in history),
            ],
            "stream": True,
        }
        if self.tools:
            payload["tools"] = self.tools

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout, connect=5.0)
        )
        pending_calls: dict[str, dict[str, Any]] = {}
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
                    if not isinstance(message, dict):
                        continue

                    content = message.get("content", "")
                    if content:
                        yield TextChunk(str(content))

                    for call in message.get("tool_calls") or []:
                        if not isinstance(call, dict):
                            continue
                        function = call.get("function")
                        if not isinstance(function, dict):
                            continue
                        name = function.get("name")
                        if not name:
                            continue
                        arguments = function.get("arguments") or {}
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                arguments = {}
                        if not isinstance(arguments, dict):
                            arguments = {}
                        entry = pending_calls.setdefault(
                            str(name), {"name": str(name), "arguments": {}}
                        )
                        entry["arguments"].update(arguments)

            if pending_calls:
                yield ToolCalls(list(pending_calls.values()))
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise OllamaConnectionError(str(exc)) from exc
        finally:
            if owns_client:
                await client.aclose()


class Conversation:
    """A conversation with the agent, including history and optional tools."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        *,
        tools: ToolRegistry | None = None,
        confirm: Confirm | None = None,
    ) -> None:
        self.client = client or OllamaClient()
        self.tools = tools or ToolRegistry()
        self.confirm = confirm
        self.messages: list[Message] = []
        if tools is not None:
            self.client.tools = self.tools.as_schema()

    def clear(self) -> None:
        """Remove all messages from the history."""
        self.messages.clear()

    def set_confirmation(self, confirm: Confirm | None) -> None:
        """Set or replace the tool-call confirmation callback."""
        self.confirm = confirm

    async def stream_answer(self, user_text: str) -> AsyncIterator[str]:
        """Yield only the assistant's text, handling tool calls internally."""
        async for event in self.stream_events(user_text):
            if isinstance(event, TextChunk):
                yield event.text

    async def stream_events(self, user_text: str) -> AsyncIterator[StreamEvent]:
        """Run the chat loop, including tool calls and confirmations."""
        start_len = len(self.messages)
        self.messages.append(Message("user", user_text))
        all_text: list[str] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                round_text: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                async for event in self.client.chat_stream(self.messages):
                    if isinstance(event, TextChunk):
                        round_text.append(event.text)
                        yield event
                    elif isinstance(event, ToolCalls):
                        tool_calls.extend(event.calls)
                        yield event

                all_text.extend(round_text)
                if not tool_calls:
                    break

                self.messages.append(
                    Message("assistant", "".join(round_text), tool_calls=tool_calls)
                )
                for call in tool_calls:
                    name = str(call.get("name", ""))
                    arguments = call.get("arguments") or {}
                    if not isinstance(arguments, dict):
                        arguments = {}
                    try:
                        result = await self.tools.call(name, arguments, self.confirm)
                    except ToolError as exc:
                        result = f"Error: {exc}"
                    self.messages.append(Message("tool", result))
                    yield ToolResultEvent(name, result)
        except OllamaError:
            del self.messages[start_len:]
            raise

        self.messages.append(Message("assistant", "".join(all_text)))
