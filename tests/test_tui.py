import asyncio
import json

import httpx
import pytest
from textual.widgets import Input, Static

from daneel.core import Conversation, OllamaClient
from daneel.i18n import STRINGS, build_system_prompt
from daneel.tools import FunctionTool, ToolRegistry
from daneel.tui import DaneelApp


def mock_http() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.dumps(
            {"message": {"role": "assistant", "content": "Привет!"}},
            ensure_ascii=False,
        )
        return httpx.Response(200, text=body + "\n")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_tui_submits_prompt_and_stores_answer() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        assert app.lang == "en"
        assert app.query_one("#prompt", Input).placeholder == STRINGS["en"][
            "prompt_placeholder"
        ]
        assert app.query_one("#hints", Static).content == STRINGS["en"]["hints"]

        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert [(m.role, m.content) for m in app.conversation.messages] == [
            ("user", "привет"),
            ("assistant", "Привет!"),
        ]
        assert app.query_one("#prompt", Input).value == ""

    await http.aclose()


async def test_tui_language_and_reply_commands() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang ru")
        await pilot.press("enter")
        await pilot.pause()
        assert app.lang == "ru"
        assert app.query_one("#prompt", Input).placeholder == STRINGS["ru"][
            "prompt_placeholder"
        ]
        assert app.query_one("#hints", Static).content == STRINGS["ru"]["hints"]

        await pilot.press(*"/reply ru")
        await pilot.press("enter")
        await pilot.pause()
        assert app.reply_language == "ru"
        assert app.conversation.client.system_prompt == build_system_prompt("ru")

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.lang == "en"

    await http.aclose()


async def test_cyrillic_key_aliases() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)), ui_language="ru")

    async with app.run_test() as pilot:
        await pilot.press("ctrl+\u0435")  # Cyrillic ye, same key as T
        await pilot.pause()
        assert app.lang == "en"

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.lang == "ru"

        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert app.conversation.messages

        await pilot.press("ctrl+\u0434")  # Cyrillic de, same key as L
        await pilot.pause()
        assert app.conversation.messages == []

    await http.aclose()


async def test_cyrillic_ctrl_c_quits() -> None:
    app = DaneelApp(Conversation(OllamaClient()))

    async with app.run_test() as pilot:
        await pilot.press("ctrl+\u0441")  # Cyrillic es, same key as C
        await pilot.pause()

    assert not app.is_running


def tool_call_app(
    ui_language: str = "en",
) -> tuple[httpx.AsyncClient, DaneelApp, list[dict]]:
    executed: list[dict] = []
    requests: list[dict] = []

    async def runner(arguments: dict) -> str:
        executed.append(arguments)
        return "ok"

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

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            body = json.dumps(
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
                                    "arguments": {"value": "hi"},
                                },
                            }
                        ],
                    },
                    "done": True,
                }
            )
        else:
            body = json.dumps(
                {"message": {"role": "assistant", "content": "Готово"}, "done": True},
                ensure_ascii=False,
            )
        return httpx.Response(200, text=body + "\n")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    conversation = Conversation(OllamaClient(client=http), tools=ToolRegistry([tool]))
    return http, DaneelApp(conversation, ui_language=ui_language), executed


async def test_tui_confirmation_allows_tool_with_yes_key() -> None:
    http, app, executed = tool_call_app()

    async with app.run_test() as pilot:
        send_task = asyncio.create_task(app.send("привет"))
        await asyncio.sleep(0.2)

        await pilot.press("enter")
        await send_task

        assert executed == [{"value": "hi"}]

    await http.aclose()


@pytest.mark.parametrize("key", ["escape", "n"])
async def test_tui_confirmation_denial_keys(key: str) -> None:
    http, app, executed = tool_call_app()

    async with app.run_test() as pilot:
        send_task = asyncio.create_task(app.send("привет"))
        await asyncio.sleep(0.2)
        await pilot.press(key)
        await send_task

        assert executed == []
        results = [m.content for m in app.conversation.messages if m.role == "tool"]
        assert results and "denied" in results[0]

    await http.aclose()


async def test_tui_confirmation_enter_approves() -> None:
    http, app, executed = tool_call_app("ru")

    async with app.run_test() as pilot:
        send_task = asyncio.create_task(app.send("привет"))
        await asyncio.sleep(0.2)

        await pilot.press("enter")
        await send_task

        assert executed == [{"value": "hi"}]

    await http.aclose()


async def test_tui_confirmation_tab_then_enter_denies() -> None:
    http, app, executed = tool_call_app()

    async with app.run_test() as pilot:
        send_task = asyncio.create_task(app.send("привет"))
        await asyncio.sleep(0.2)

        await pilot.press("tab")
        await pilot.press("enter")
        await send_task

        assert executed == []

    await http.aclose()


async def test_tui_theme_command() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        assert app.current_theme.name == "daneel"

        await pilot.press(*"/theme dracula")
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_theme.name == "dracula"

        await pilot.press(*"/theme")
        await pilot.press("enter")
        await pilot.pause()
        assert app.current_theme.name == "dracula"

    await http.aclose()
