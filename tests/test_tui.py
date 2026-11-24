import json

import httpx
from textual.widgets import Input, Static

from daneel.core import Conversation, OllamaClient
from daneel.i18n import STRINGS, build_system_prompt
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
