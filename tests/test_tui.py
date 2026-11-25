import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pyperclip
import pytest
from rich.text import Text
from textual.widgets import OptionList, Static

from daneel import clipboard
from daneel.commands import COMMANDS
from daneel.config import Preferences, PreferencesStore
from daneel.core import Conversation, Message, OllamaClient
from daneel.i18n import STRINGS, build_system_prompt
from daneel.theme import available_themes
from daneel.tools import FunctionTool, ToolRegistry
from daneel.tui import DaneelApp, PromptInput


def mock_http() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.dumps(
            {"message": {"role": "assistant", "content": "Привет!"}},
            ensure_ascii=False,
        )
        return httpx.Response(200, text=body + "\n")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def capture_notifications(monkeypatch: pytest.MonkeyPatch, app: DaneelApp) -> list[str]:
    """Collect notification messages before they expire."""
    messages: list[str] = []
    original = app.notify

    def notify(message: str, **kwargs: Any) -> None:
        messages.append(str(message))
        original(message, **kwargs)

    monkeypatch.setattr(app, "notify", notify)
    return messages


async def test_tui_submits_prompt_and_stores_answer() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        assert app.lang == "en"
        assert app.query_one("#prompt", PromptInput).placeholder == STRINGS["en"][
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
        assert app.query_one("#prompt", PromptInput).text == ""

    await http.aclose()


async def test_chat_messages_have_no_speaker_labels() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.query_one(".message.user", Static).content == "привет"
        assert app.query_one(".message.assistant", Static).content == "Привет!"

    await http.aclose()


async def test_language_change_notifies_without_chat_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"/lang ru")
        await pilot.press("enter")
        await pilot.pause()

        assert "Язык интерфейса: RU" in notified
        app.screen.text_select_all()
        assert "Язык интерфейса: RU" not in (app.screen.get_selected_text() or "")

    await http.aclose()


async def test_tui_language_and_reply_commands() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang ru")
        await pilot.press("enter")
        await pilot.pause()
        assert app.lang == "ru"
        assert app.query_one("#prompt", PromptInput).placeholder == STRINGS["ru"][
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


async def test_copy_command_copies_visible_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.press(*"/lang en")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*"/copy")
        await pilot.press("enter")
        await pilot.press("enter")

        assert "привет" in app.clipboard
        assert "Привет!" in app.clipboard
        assert "running offline" not in app.clipboard
        assert "Interface language: EN" in notified
        assert STRINGS["en"]["copied"] in notified

    await http.aclose()


async def test_copy_last_copies_only_the_answer() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.press(*"/copy last")
        await pilot.press("enter")

        assert app.clipboard == "Привет!"

    await http.aclose()


async def test_copy_last_uses_the_most_recent_answer() -> None:
    answers = ["First", "Second"]
    calls = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        content = answers[min(calls[0], len(answers) - 1)]
        calls[0] += 1
        body = json.dumps(
            {"message": {"role": "assistant", "content": content}, "done": True}
        )
        return httpx.Response(200, text=body + "\n")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        for message in ("one", "two"):
            await pilot.press(*message)
            await pilot.press("enter")
            await pilot.pause(0.2)
        await pilot.press(*"/copy last")
        await pilot.press("enter")

        assert app.clipboard == "Second"

    await http.aclose()


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_slash_palette_lists_commands_without_help(language: str) -> None:
    http = mock_http()
    app = DaneelApp(
        Conversation(OllamaClient(client=http)), ui_language=language
    )

    async with app.run_test() as pilot:
        await pilot.press(*"/")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.styles.display == "block"
        assert popup.option_count == len(COMMANDS)
        assert any(
            "/copy" in popup.get_option_at_index(index).prompt.plain
            for index in range(popup.option_count)
        )
        assert all(
            "/help" not in popup.get_option_at_index(index).prompt.plain
            for index in range(popup.option_count)
        )

        await pilot.press("escape")
        await pilot.pause()
        assert popup.styles.display == "none"

    await http.aclose()


async def test_copy_command_with_empty_chat_reports_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"/copy")
        await pilot.press("enter")
        await pilot.press("enter")

        assert app.clipboard == ""
        assert STRINGS["en"]["nothing_to_copy"] in notified

    await http.aclose()


async def test_copy_command_reports_note_in_russian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(
        Conversation(OllamaClient(client=http)), ui_language="ru"
    )
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"/copy")
        await pilot.press("enter")
        await pilot.press("enter")

        assert STRINGS["ru"]["nothing_to_copy"] in notified

    await http.aclose()


async def test_clear_resets_the_copy_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        await pilot.press("ctrl+l")
        await pilot.pause()
        await pilot.press(*"/copy")
        await pilot.press("enter")
        await pilot.press("enter")

        assert app.clipboard == ""
        assert STRINGS["en"]["nothing_to_copy"] in notified

    await http.aclose()


async def test_right_click_copies_selected_text(monkeypatch: pytest.MonkeyPatch) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        with monkeypatch.context() as patch:
            patch.setattr(app.screen, "get_selected_text", lambda: "selected text")
            await pilot.click("#log", button=3)

        assert app.clipboard == "selected text"
        assert STRINGS["en"]["copied"] in notified

    await http.aclose()


async def test_right_click_copies_real_selection() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        app.screen.text_select_all()
        expected = app.screen.get_selected_text()
        assert expected

        await pilot.click("#log", button=3)

        assert app.clipboard == expected

    await http.aclose()


async def test_right_click_without_selection_does_not_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(
        Conversation(OllamaClient(client=http)), ui_language="ru"
    )
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        with monkeypatch.context() as patch:
            patch.setattr(app.screen, "get_selected_text", lambda: None)
            await pilot.click("#log", button=3)

        assert app.clipboard == ""
        assert STRINGS["ru"]["nothing_selected"] in notified

    await http.aclose()


def test_notifications_expire_quickly() -> None:
    assert DaneelApp.NOTIFICATION_TIMEOUT == 2.0


async def test_exchange_is_saved_to_current_session() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)

        sessions = app.store.list_sessions()
        assert len(sessions) == 1
        assert [
            (message.role, message.content)
            for message in app.store.load_messages(sessions[0].id)
        ] == [("user", "привет"), ("assistant", "Привет!")]

    await http.aclose()


async def test_sessions_palette_loads_selected_session() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    old_id = app.store.create_session("Old chat")
    app.store.append_messages(
        old_id, [Message("user", "old question"), Message("assistant", "old answer")]
    )

    async with app.run_test() as pilot:
        await pilot.press(*"/sessions")
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.styles.display == "block"
        assert popup.option_count == 1
        assert "Old chat" in popup.get_option_at_index(0).prompt.plain

        await pilot.press("enter")
        await pilot.pause()

        assert app.current_session_id == old_id
        assert [
            (message.role, message.content)
            for message in app.conversation.messages
        ] == [("user", "old question"), ("assistant", "old answer")]
        app.screen.text_select_all()
        assert "old question" in (app.screen.get_selected_text() or "")

    await http.aclose()


async def test_session_delete_key_asks_confirmation_and_refreshes_palette(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)
    old_id = app.store.create_session("Old chat")

    async with app.run_test() as pilot:
        await pilot.press(*"/sessions")
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.option_count == 1

        delete_task = asyncio.create_task(pilot.press("delete"))
        await asyncio.sleep(0.2)
        await pilot.press("enter")
        await delete_task
        await pilot.pause()

        assert app.store.get_session(old_id) is None
        assert f"Session #{old_id} deleted." in notified
        assert popup.option_count == 0

    await http.aclose()


async def test_session_delete_icon_asks_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)
    old_id = app.store.create_session("Old chat")

    async with app.run_test() as pilot:
        await pilot.press(*"/sessions")
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        icon_x = popup.get_option_at_index(0).prompt.plain.index("✕") + 2
        delete_task = asyncio.create_task(
            pilot.click("#suggestions", offset=(icon_x, 0))
        )
        await asyncio.sleep(0.2)
        await pilot.press("enter")
        await delete_task
        await pilot.pause()

        assert app.store.get_session(old_id) is None
        assert f"Session #{old_id} deleted." in notified
        assert app.current_session_id is None

    await http.aclose()


async def test_new_command_starts_fresh_session() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert app.current_session_id is not None

        await pilot.press(*"/new")
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_session_id is None
        assert app.conversation.messages == []

    await http.aclose()


async def test_slash_shows_and_hides_command_suggestions() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.styles.display == "block"
        assert popup.option_count == len(COMMANDS)

        await pilot.press("escape")
        await pilot.pause()
        assert popup.styles.display == "none"

    await http.aclose()


async def test_command_suggestions_filter_and_accept() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/c")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.option_count == 2
        assert popup.highlighted == 0

        await pilot.press("down")
        await pilot.pause()
        assert popup.highlighted == 1

        await pilot.press("enter")
        await pilot.pause()

        prompt = app.query_one("#prompt", PromptInput)
        assert prompt.text == "/copy "
        assert popup.styles.display == "block"
        assert popup.option_count == 2

    await http.aclose()


async def test_command_suggestion_click_accepts() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#suggestions", offset=(2, 1))
        await pilot.pause()

        assert app.lang == "ru"
        assert app.query_one("#prompt", PromptInput).text == ""

    await http.aclose()


async def test_typing_space_hides_command_suggestions() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.pause()
        assert app.query_one("#suggestions", OptionList).styles.display == "block"

        await pilot.press(" ")
        await pilot.pause()
        assert app.query_one("#suggestions", OptionList).styles.display == "none"

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


async def test_prompt_grows_with_multiline_content() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt", PromptInput)
        assert prompt.styles.height.value == PromptInput.MIN_HEIGHT

        prompt.load_text("line one\nline two\nline three")
        await pilot.pause()

        assert prompt.styles.height.value == 5

    await http.aclose()


async def test_prompt_submits_multiline_text_on_enter() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt", PromptInput)
        prompt.load_text("first line\nsecond line\nthird line")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause(0.2)

        assert app.conversation.messages[0].content == (
            "first line\nsecond line\nthird line"
        )
        assert prompt.text == ""

    await http.aclose()


async def test_right_click_in_input_pastes_system_clipboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)
    monkeypatch.setattr(clipboard.pyperclip, "paste", lambda: "system text")

    async with app.run_test() as pilot:
        await pilot.click("#prompt", button=3)

        assert app.query_one("#prompt", PromptInput).text == "system text"
        assert notified == []

    await http.aclose()


async def test_right_click_in_input_falls_back_to_app_clipboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    def unavailable() -> str:
        raise pyperclip.PyperclipException("no clipboard utility")

    monkeypatch.setattr(clipboard.pyperclip, "paste", unavailable)
    app.copy_to_clipboard("internal text")

    async with app.run_test() as pilot:
        await pilot.click("#prompt", button=3)

        assert app.query_one("#prompt", PromptInput).text == "internal text"

    await http.aclose()


async def test_right_click_in_input_with_empty_clipboard_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)
    monkeypatch.setattr(clipboard.pyperclip, "paste", lambda: "")

    async with app.run_test() as pilot:
        await pilot.click("#prompt", button=3)

        assert app.query_one("#prompt", PromptInput).text == ""
        assert notified == []

    await http.aclose()


async def test_suggestion_rows_have_two_columns_and_soft_side_bars() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        row = popup.get_option_at_index(0).prompt
        assert isinstance(row, Text)
        assert row.plain.startswith("/lang")
        assert "switch interface language" in row.plain
        assert any(
            "dim" in str(span.style) for span in row.spans if span.style
        )

        assert popup.styles.border_top[0] in ("", "none")
        assert popup.styles.border_left[0] == "vkey"
        assert popup.styles.border_right[0] == "vkey"
        hints = app.query_one("#hints", Static)
        assert hints.styles.border_top[0] in ("", "none")
        assert hints.styles.border_left[0] == "vkey"
        assert hints.styles.border_right[0] == "vkey"

    await http.aclose()


async def test_lang_choices_apply_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        prompt = app.query_one("#prompt", PromptInput)
        assert popup.styles.display == "block"
        assert popup.option_count == 2
        assert prompt.text == "/lang "
        assert popup.get_option_at_index(0).prompt.plain.startswith("en")

        await pilot.press("down")
        await pilot.pause()
        assert popup.highlighted == 1

        await pilot.press("enter")
        await pilot.pause()

        assert app.lang == "ru"
        assert prompt.text == ""
        assert popup.styles.display == "none"
        assert "Язык интерфейса: RU" in notified

    await http.aclose()


async def test_lang_choices_filter_by_typed_letter() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.press("enter")
        await pilot.press("r")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.option_count == 1
        assert popup.get_option_at_index(0).prompt.plain.startswith("ru")

        await pilot.press("enter")
        await pilot.pause()
        assert app.lang == "ru"

    await http.aclose()


async def test_reply_choices_apply_immediately() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/reply")
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.option_count == 3

        await pilot.press(*"ru")
        await pilot.pause()
        assert popup.option_count == 1

        await pilot.press("enter")
        await pilot.pause()
        assert app.reply_language == "ru"
        assert app.conversation.client.system_prompt == build_system_prompt("ru")

    await http.aclose()


async def test_tui_settings_changes_are_saved(tmp_path: Path) -> None:
    http = mock_http()
    path = tmp_path / "settings.json"
    app = DaneelApp(
        Conversation(OllamaClient(client=http)),
        preferences=PreferencesStore(path),
    )

    async with app.run_test() as pilot:
        await pilot.press(*"/lang ru")
        await pilot.press("enter")
        await pilot.press(*"/reply ru")
        await pilot.press("enter")
        await pilot.press(*"/theme dracula")
        await pilot.press("enter")
        await pilot.pause()

    assert PreferencesStore.load(path).preferences == Preferences(
        ui_language="ru", reply_language="ru", theme="dracula"
    )

    await http.aclose()


async def test_language_toggle_is_saved(tmp_path: Path) -> None:
    http = mock_http()
    path = tmp_path / "settings.json"
    app = DaneelApp(
        Conversation(OllamaClient(client=http)),
        preferences=PreferencesStore(path),
    )

    async with app.run_test() as pilot:
        await pilot.press("ctrl+t")
        await pilot.pause()

    assert PreferencesStore.load(path).preferences.ui_language == "ru"

    await http.aclose()


async def test_empty_choice_filter_hides_menu_and_backspace_restores_it() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.press("enter")
        await pilot.press(*"zz")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.styles.display == "none"

        await pilot.press("backspace")
        await pilot.press("backspace")
        await pilot.pause()
        assert popup.styles.display == "block"
        assert popup.option_count == 2

    await http.aclose()


async def test_theme_choices_filter_and_apply() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/theme")
        await pilot.press("enter")
        await pilot.pause()

        popup = app.query_one("#suggestions", OptionList)
        assert popup.option_count == len(available_themes())

        await pilot.press(*"dra")
        await pilot.pause()
        assert popup.option_count == 1

        await pilot.press("enter")
        await pilot.pause()
        assert app.current_theme.name == "dracula"

    await http.aclose()


@pytest.mark.parametrize("name", ["load", "help"])
async def test_removed_commands_are_reported_as_unknown(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))
    notified = capture_notifications(monkeypatch, app)

    async with app.run_test() as pilot:
        await pilot.press(*f"/{name} 1")
        await pilot.press("enter")
        await pilot.pause()

        assert STRINGS["en"]["unknown_command"].format(command=name) in notified

    await http.aclose()


async def test_argumentless_command_runs_from_menu() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"привет")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert app.current_session_id is not None

        await pilot.press(*"/new")
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_session_id is None
        assert app.conversation.messages == []
        assert app.query_one("#prompt", PromptInput).text == ""

    await http.aclose()


async def test_escape_closes_choice_menu() -> None:
    http = mock_http()
    app = DaneelApp(Conversation(OllamaClient(client=http)))

    async with app.run_test() as pilot:
        await pilot.press(*"/lang")
        await pilot.press("enter")
        await pilot.pause()
        popup = app.query_one("#suggestions", OptionList)
        assert popup.styles.display == "block"

        await pilot.press("escape")
        await pilot.pause()
        assert popup.styles.display == "none"
        assert app.lang == "en"

    await http.aclose()
