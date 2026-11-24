"""Terminal interface for Daneel.AI, built with Textual."""

from __future__ import annotations

from typing import cast

from rich.markup import escape
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Input, Static

from .confirmation import install_confirmation, render_arguments
from .core import Conversation, OllamaError
from .i18n import ReplyLanguage, UILanguage, build_system_prompt, t
from .theme import available_themes, register_themes
from .tools import Arguments


class ToolConfirmationScreen(ModalScreen[bool]):
    """Modal dialog asking whether a tool call may run."""

    CSS = """
    ToolConfirmationScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $warning;
        background: $surface;
    }
    #confirm-actions {
        height: auto;
        align: center middle;
    }
    Button {
        margin: 1;
    }
    """

    def __init__(self, question: str, language: UILanguage) -> None:
        super().__init__()
        self.question = question
        self.language = language

    def compose(self) -> ComposeResult:
        """Build the question and the two decision buttons."""
        with Vertical(id="confirm-dialog"):
            yield Static(
                f"[bold]{t(self.language, 'confirm_title')}[/]",
                id="confirm-title",
            )
            yield Static(self.question, id="confirm-question")
            with Horizontal(id="confirm-actions"):
                yield Button(
                    t(self.language, "confirm_allow"),
                    id="allow",
                    variant="success",
                )
                yield Button(
                    t(self.language, "confirm_deny"),
                    id="deny",
                    variant="error",
                )

    def on_mount(self) -> None:
        """Localize bindings and focus Allow so that Enter approves."""
        deny = t(self.language, "confirm_deny")
        self._bindings.bind("escape", "deny", deny)
        self._bindings.bind("n", "deny", deny)
        self.refresh_bindings()
        self.query_one("#allow", Button).focus()

    @on(Button.Pressed, "#allow")
    def allow(self) -> None:
        """Approve the tool call."""
        self.dismiss(True)

    @on(Button.Pressed, "#deny")
    def deny(self) -> None:
        """Reject the tool call."""
        self.dismiss(False)

    def action_deny(self) -> None:
        """Reject from the keyboard."""
        self.deny()


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
        padding: 1 1;
        background: $footer-background;
        border: none;
        border-left: heavy $primary;
        content-align: left middle;
    }
    #prompt:focus {
        border: none;
        border-left: heavy $primary;
        background-tint: transparent;
    }
    #hints {
        height: 3;
        margin: 1 2 1 2;
        padding: 0 1;
        border: round $primary;
        content-align: left middle;
        color: $footer-description-foreground;
        background: $footer-background;
    }
    """

    def __init__(
        self,
        conversation: Conversation,
        ui_language: UILanguage = "en",
        reply_language: ReplyLanguage = "auto",
        theme_name: str = "daneel",
    ) -> None:
        super().__init__()
        self.conversation = conversation
        self.lang = ui_language
        self.reply_language = reply_language
        self.theme_name = theme_name
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
        """Register themes, apply the selected language, and focus the input."""
        register_themes(self)
        self.theme = self.theme_name
        self._apply_language()
        install_confirmation(self.conversation, self.confirm_tool_call)
        self.query_one("#prompt", Input).focus()

    async def confirm_tool_call(self, name: str, arguments: Arguments) -> bool:
        """Ask the user in a modal whether the tool call may run."""
        rendered = render_arguments(arguments)
        question = t(
            self.lang, "confirm_tool_question", name=name, arguments=rendered
        )

        async def ask() -> bool:
            return await self.push_screen_wait(
                ToolConfirmationScreen(question, self.lang)
            )

        allowed = await self.run_worker(ask()).wait()
        if not allowed:
            await self._note(t(self.lang, "tool_denied", name=name))
        return allowed

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
        elif name == "theme":
            if not argument:
                await self._note(
                    t(self.lang, "theme_list", themes=", ".join(available_themes()))
                )
            elif argument in available_themes():
                self.theme_name = argument
                self.theme = argument
                await self._note(t(self.lang, "theme_changed", theme=argument))
            else:
                await self._note(t(self.lang, "theme_unknown", theme=argument))
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
