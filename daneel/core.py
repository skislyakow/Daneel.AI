"""Ядро Daneel.AI: работа с Ollama и состояние диалога."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal

import httpx

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
SYSTEM_PROMPT = (
    "Ты — Р. Даниел Оливо (Daneel.AI), локальный ИИ-агент, названный в честь робота-детектива Исаака Азимова. "
    "Твоя цель — помогать пользователю решать домашние и рабочие задачи. "
    "Отвечай кратко, четко, по делу и на русском языке."
)

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class Message:
    """Одно сообщение в истории диалога."""

    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class OllamaError(RuntimeError):
    """Ошибка при запросе к Ollama."""


class OllamaConnectionError(OllamaError):
    """Не удалось связаться со сервисом Ollama."""


class OllamaClient:
    """Асинхронный клиент Ollama с потоковым ответом."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
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
        """Отправить историю в /api/chat и вернуть поток кусков ответа."""
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
                    raise OllamaError(
                        f"Ollama вернул код {response.status_code}: {body[:200]}"
                    )

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
            raise OllamaConnectionError(
                "Не удалось подключиться к Ollama. Проверьте, запущен ли сервис."
            ) from exc
        finally:
            if owns_client:
                await client.aclose()


class Conversation:
    """Диалог с агентом: хранит историю и добавляет ответы в неё."""

    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()
        self.messages: list[Message] = []

    def clear(self) -> None:
        self.messages.clear()

    async def stream_answer(self, user_text: str) -> AsyncIterator[str]:
        """Записать реплику пользователя и вернуть поток ответа Даниела."""
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
