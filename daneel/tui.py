"""Terminal interface for Daneel.AI, built with Textual."""

from __future__ import annotations

from typing import cast

from rich.markup import escape
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Header, Input, Static

from .core import Conversation, OllamaError
from .i18n import ReplyLanguage, UILanguage, build_system_prompt, t


class DaneelApp(App[None]):
    """Full-screen terminal chat with localized strings and local commands."""

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
    .note {
        color: $warning;
    }
    #composer {
        dock: bottom;
        height: auto;
    }
    #prompt {
        margin: 0 2;
    }
    #hints {
        height: auto;
        padding: 0 2 1 2;
        color: $footer-description-foreground;
        background: $footer-background;
    }
    """

    def __init__(
        self,
        conversation: Conversation,
        ui_language: UILanguage = "en",
        reply_language: ReplyLanguage = "auto",
    ) -> None:
        super().__init__()
        self.conversation = conversation
        self.lang = ui_language
        self.reply_language = reply_language
        self._busy = False
        self._welcome: Static | None = None
        self._hints: Static | None = None

    def compose(self) -> ComposeResult:
        """Build the initial widget tree."""
        yield Header()
        with VerticalScroll(id="log"):
            self._welcome = Static(t(self.lang, "welcome"), classes="message")
            yield self._welcome
        with Vertical(id="composer"):
            yield Input(placeholder=t(self.lang, "prompt_placeholder"), id="prompt")
            self._hints = Static(t(self.lang, "hints"), id="hints")
            yield self._hints

    def on_mount(self) -> None:
        """Apply the selected language and focus the input."""
        self._apply_language()
        self.query_one("#prompt", Input).focus()

    def _apply_language(self) -> None:
        """Update language-dependent widgets and key bindings."""
        if self._welcome is not None:
            self._welcome.update(t(self.lang, "welcome"))
        if self._hints is not None:
            self._hints.update(t(self.lang, "hints"))
        self.query_one("#prompt", Input).placeholder = t(
            self.lang, "prompt_placeholder"
        )
        self.sub_title = t(self.lang, "thinking") if self._busy else ""

        clear = t(self.lang, "clear_binding")
        toggle = t(self.lang, "toggle_binding")
        quit_text = t(self.lang, "quit_binding")
        # Cyrillic aliases match the same physical keys under the Russian layout.
        self._bindings.bind("ctrl+l", "clear", clear)
        self._bindings.bind("ctrl+\u0434", "clear", clear)
        self._bindings.bind("ctrl+t", "toggle_language", toggle)
        self._bindings.bind("ctrl+\u0435", "toggle_language", toggle)
        self._bindings.bind("ctrl+c", "quit", quit_text, priority=True)
        self._bindings.bind("ctrl+\u0441", "quit", quit_text, priority=True)
        self.refresh_bindings()

    async def _note(self, text: str) -> None:
        """Show a local system message in the chat log."""
        log = self.query_one("#log", VerticalScroll)
        await log.mount(
            Static(
                f"[dim]{t(self.lang, 'note')}:[/] {escape(text)}",
                classes="message note",
            )
        )
        log.scroll_end(animate=False)

    @on(Input.Submitted, "#prompt")
    async def handle_submit(self, event: Input.Submitted) -> None:
        """Handle either a local command or a message for the agent."""
        if self._busy:
            return
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        if text.startswith("/"):
            await self.handle_command(text)
            return
        await self.send(text)

    async def handle_command(self, text: str) -> None:
        """Process a local slash command without contacting Ollama."""
        parts = text[1:].split()
        name = parts[0].lower() if parts else ""
        argument = parts[1].lower() if len(parts) > 1 else ""

        if name == "lang":
            if argument in {"en", "ru"}:
                self.lang = cast(UILanguage, argument)
                self._apply_language()
                await self._note(
                    t(self.lang, "lang_changed", language=argument.upper())
                )
            else:
                await self._note(t(self.lang, "usage_lang"))
        elif name == "reply":
            if argument in {"auto", "en", "ru"}:
                self.reply_language = cast(ReplyLanguage, argument)
                self.conversation.client.system_prompt = build_system_prompt(argument)
                await self._note(
                    t(self.lang, "reply_changed", language=argument.upper())
                )
            else:
                await self._note(t(self.lang, "usage_reply"))
        elif name == "clear":
            await self.action_clear()
        elif name == "help":
            await self._note(t(self.lang, "help_text"))
        else:
            await self._note(t(self.lang, "unknown_command", command=name))

    async def send(self, text: str) -> None:
        """Send a message and render the streaming answer."""
        prompt = self.query_one("#prompt", Input)
        log = self.query_one("#log", VerticalScroll)
        self._busy = True
        prompt.disabled = True
        self.sub_title = t(self.lang, "thinking")

        await log.mount(
            Static(
                f"[bold]{t(self.lang, 'you')}:[/] {escape(text)}",
                classes="message user",
            )
        )
        answer = Static(
            f"[bold green]{t(self.lang, 'daneel')}:[/] ", classes="message assistant"
        )
        await log.mount(answer)

        received = ""
        try:
            async for chunk in self.conversation.stream_answer(text):
                received += chunk
                answer.update(
                    f"[bold green]{t(self.lang, 'daneel')}:[/] {escape(received)}"
                )
                log.scroll_end(animate=False)
        except OllamaError as exc:
            message = t(self.lang, exc.message_key, detail=exc.detail)
            answer.update(
                f"[bold red]{t(self.lang, 'error_prefix')}:[/] {escape(message)}"
            )
            answer.set_class(True, "error")
        finally:
            self._busy = False
            prompt.disabled = False
            self.sub_title = ""
            prompt.focus()

    async def action_toggle_language(self) -> None:
        """Switch between English and Russian without restarting."""
        if self._busy:
            return
        self.lang = "ru" if self.lang == "en" else "en"
        self._apply_language()
        await self._note(t(self.lang, "lang_changed", language=self.lang.upper()))

    async def action_clear(self) -> None:
        """Clear the conversation and reset the chat log."""
        if self._busy:
            return
        self.conversation.clear()
        log = self.query_one("#log", VerticalScroll)
        for child in list(log.children):
            child.remove()
        self._welcome = Static(t(self.lang, "welcome"), classes="message")
        await log.mount(self._welcome)
