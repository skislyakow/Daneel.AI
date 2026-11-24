import json

import httpx
from textual.widgets import Input

from daneel.core import Conversation, OllamaClient
from daneel.tui import DaneelApp


async def test_tui_submits_prompt_and_stores_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.dumps(
            {"message": {"role": "assistant", "content": "Привет!"}},
            ensure_ascii=False,
        )
        return httpx.Response(200, text=body + "\n")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert [(m.role, m.content) for m in app.conversation.messages] == [
            ("user", "привет"),
            ("assistant", "Привет!"),
        ]
        assert app.query_one("#prompt", Input).value == ""

    await http.aclose()
