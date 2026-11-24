import json

import httpx
import pytest

from daneel.core import Conversation, OllamaClient, OllamaConnectionError
from daneel.i18n import DEFAULT_REPLY_LANGUAGE, build_system_prompt


def streaming_response(chunks: list[dict]) -> httpx.Response:
    body = "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks)
    return httpx.Response(200, text=body + "\n")


async def test_stream_answer_accumulates_and_sends_history() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return streaming_response(
            [
                {"message": {"role": "assistant", "content": "При"}},
                {"message": {"role": "assistant", "content": "вет"}},
                {"done": True, "done_reason": "stop"},
            ]
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(OllamaClient(client=http))

    parts = [chunk async for chunk in conversation.stream_answer("Здравствуй")]

    assert "".join(parts) == "Привет"
    assert [(m.role, m.content) for m in conversation.messages] == [
        ("user", "Здравствуй"),
        ("assistant", "Привет"),
    ]
    assert seen[0]["stream"] is True
    assert seen[0]["messages"][0] == {
        "role": "system",
        "content": build_system_prompt(DEFAULT_REPLY_LANGUAGE),
    }
    assert seen[0]["messages"][1] == {"role": "user", "content": "Здравствуй"}
    await http.aclose()


async def test_connection_error_rolls_back_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(OllamaClient(client=http))

    with pytest.raises(OllamaConnectionError):
        [chunk async for chunk in conversation.stream_answer("Привет")]

    assert conversation.messages == []
    await http.aclose()
