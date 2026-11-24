import json

import httpx
import pytest

from daneel import config
from daneel.config import Settings
from daneel.core import (
    MAX_TOOL_ROUNDS,
    Conversation,
    OllamaClient,
    OllamaConnectionError,
    TextChunk,
    ToolCalls,
    ToolResultEvent,
    ToolRoundLimitError,
)
from daneel.i18n import DEFAULT_REPLY_LANGUAGE, build_system_prompt
from daneel.tools import FunctionTool, ToolRegistry


def streaming_response(chunks: list[dict]) -> httpx.Response:
    body = "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks)
    return httpx.Response(200, text=body + "\n")


def test_client_defaults_follow_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEFAULT_BASE_URL", "http://example:11434")
    monkeypatch.setattr(config, "DEFAULT_MODEL", "test-model")

    settings = Settings.from_env({})
    client = OllamaClient()

    assert client.base_url == settings.base_url
    assert client.model == settings.model


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


async def test_tool_call_loop_executes_confirmed_tool() -> None:
    executed: list[dict] = []

    async def runner(arguments: dict) -> str:
        executed.append(arguments)
        return f"got {arguments['value']}"

    tool = FunctionTool(
        name="echo",
        description="Echo a value",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        runner=runner,
    )
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if len(seen) == 1:
            return streaming_response(
                [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "echo",
                                        "arguments": {"value": "hi"},
                                    }
                                }
                            ],
                        },
                        "done": False,
                    },
                    {"message": {"role": "assistant", "content": ""}, "done": True},
                ]
            )
        return streaming_response(
            [
                {
                    "message": {"role": "assistant", "content": "Готово"},
                    "done": True,
                }
            ]
        )

    async def confirm(name: str, arguments: dict) -> bool:
        assert name == "echo"
        return True

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(
        OllamaClient(client=http),
        tools=ToolRegistry([tool]),
        confirm=confirm,
    )

    parts = [chunk async for chunk in conversation.stream_answer("Скажи привет")]

    assert "".join(parts) == "Готово"
    assert executed == [{"value": "hi"}]
    assert seen[0]["tools"][0]["function"]["name"] == "echo"
    assert any(m.role == "tool" and m.content == "got hi" for m in conversation.messages)
    await http.aclose()


@pytest.mark.parametrize("with_ids", [True, False])
async def test_parallel_calls_to_same_tool_stay_separate(with_ids: bool) -> None:
    executed: list[dict] = []

    async def runner(arguments: dict) -> str:
        executed.append(arguments)
        return f"echo:{arguments['value']}"

    tool = FunctionTool(
        name="echo",
        description="Echo a value",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        runner=runner,
    )
    requests: list[dict] = []
    calls = [
        {"function": {"index": 0, "name": "echo", "arguments": {"value": "one"}}},
        {"function": {"index": 1, "name": "echo", "arguments": {"value": "two"}}},
    ]
    if with_ids:
        calls[0]["id"] = "call_one"
        calls[1]["id"] = "call_two"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return streaming_response(
                [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": calls,
                        },
                        "done": False,
                    },
                    {"message": {"role": "assistant", "content": ""}, "done": True},
                ]
            )
        return streaming_response(
            [{"message": {"role": "assistant", "content": "Готово"}, "done": True}]
        )

    async def confirm(name: str, arguments: dict) -> bool:
        return True

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(
        OllamaClient(client=http),
        tools=ToolRegistry([tool]),
        confirm=confirm,
    )

    events = [event async for event in conversation.stream_events("Два вызова")]

    assert "".join(e.text for e in events if isinstance(e, TextChunk)) == "Готово"
    asserted_calls = [event.calls for event in events if isinstance(event, ToolCalls)]
    assert len(asserted_calls) == 1
    assert [call["arguments"]["value"] for call in asserted_calls[0]] == ["one", "two"]
    assert [(e.name, e.result) for e in events if isinstance(e, ToolResultEvent)] == [
        ("echo", "echo:one"),
        ("echo", "echo:two"),
    ]
    assert executed == [{"value": "one"}, {"value": "two"}]
    assert [m.content for m in conversation.messages if m.role == "tool"] == [
        "echo:one",
        "echo:two",
    ]

    assert len(requests) == 2
    sent_calls = next(
        message["tool_calls"]
        for message in requests[1]["messages"]
        if message["role"] == "assistant" and message.get("tool_calls")
    )
    assert [call["function"]["arguments"]["value"] for call in sent_calls] == [
        "one",
        "two",
    ]
    tool_messages = [m for m in requests[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_name"] for m in tool_messages] == ["echo", "echo"]
    await http.aclose()


async def test_tool_round_limit_raises_and_keeps_history() -> None:
    async def runner(arguments: dict) -> str:
        return "ok"

    tool = FunctionTool(
        name="echo",
        description="Echo a value",
        parameters={"type": "object", "properties": {}, "required": []},
        runner=runner,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return streaming_response(
            [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call",
                                "function": {
                                    "index": 0,
                                    "name": "echo",
                                    "arguments": {},
                                },
                            }
                        ],
                    },
                    "done": True,
                }
            ]
        )

    async def confirm(name: str, arguments: dict) -> bool:
        return True

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(
        OllamaClient(client=http),
        tools=ToolRegistry([tool]),
        confirm=confirm,
    )

    with pytest.raises(ToolRoundLimitError):
        [event async for event in conversation.stream_events("Цикл")]

    assert conversation.messages[0].role == "user"
    assert len([m for m in conversation.messages if m.role == "tool"]) == MAX_TOOL_ROUNDS
    await http.aclose()
