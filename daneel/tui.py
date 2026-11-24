"""Терминальный интерфейс Daneel.AI на Textual."""

from __future__ import annotations

from rich.markup import escape
from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from .core import Conversation, OllamaError

WELCOME = (
    "🤖 [bold cyan]Daneel.AI[/] — локальный агент, работающий офлайн.\n"
    "[dim]Введите сообщение и нажмите Enter. Ctrl+L — очистить диалог, Ctrl+C — выход.[/]"
)


class DaneelApp(App[None]):
    TITLE = "Daneel.AI"
    CSS = """
    Screen {
        background: $surface;
    }
    #log {
        height: 1fr;
        padding: 1 2;
    }
    .message {
        margin-bottom: 1;
        width: 100%;
    }
    .user {
        color: $text;
    }
    .assistant {
        color: $success;
    }
    .error {
        color: $error;
    }
    #prompt {
        dock: bottom;
        margin: 0 2 1 2;
    }
    """

    BINDINGS = [
        ("ctrl+l", "clear", "Очистить"),
        ("ctrl+c", "quit", "Выход"),
    ]

    def __init__(self, conversation: Conversation) -> None:
        super().__init__()
        self.conversation = conversation
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="log"):
            yield Static(WELCOME, classes="message")
        yield Input(placeholder="Сообщение... (Enter — отправить)", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#prompt", Input).focus()

    @on(Input.Submitted, "#prompt")
    async def handle_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._busy:
            return
        event.input.value = ""
        await self.send(text)

    async def send(self, text: str) -> None:
        """Отправить реплику и потоково вывести ответ."""
        prompt = self.query_one("#prompt", Input)
        log = self.query_one("#log", VerticalScroll)
        self._busy = True
        prompt.disabled = True
        self.sub_title = "думает…"

        await log.mount(Static(f"[bold]Вы:[/] {escape(text)}", classes="message user"))
        answer = Static("[bold green]Даниел:[/] ", classes="message assistant")
        await log.mount(answer)

        received = ""
        try:
            async for chunk in self.conversation.stream_answer(text):
                received += chunk
                answer.update(f"[bold green]Даниел:[/] {escape(received)}")
                log.scroll_end(animate=False)
        except OllamaError as exc:
            answer.update(f"[bold red]Ошибка:[/] {escape(str(exc))}")
            answer.set_class(True, "error")
        finally:
            self._busy = False
            prompt.disabled = False
            self.sub_title = ""
            prompt.focus()

    async def action_clear(self) -> None:
        if self._busy:
            return
        self.conversation.clear()
        log = self.query_one("#log", VerticalScroll)
        for child in list(log.children):
            child.remove()
        await log.mount(Static(WELCOME, classes="message"))
