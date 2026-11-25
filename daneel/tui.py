"""Terminal interface for Daneel.AI, built with Textual."""

from __future__ import annotations

from typing import cast

from rich.markup import escape
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import MouseDown
from textual.message import Message
from textual.notifications import SeverityLevel
from textual.screen import ModalScreen
from textual.widgets import Button, Header, OptionList, Static, TextArea
from textual.widgets._option_list import Option

from .clipboard import read_text
from .confirmation import install_confirmation, render_arguments
from .core import Conversation, Message as ChatMessage, OllamaError
from .i18n import ReplyLanguage, UILanguage, build_system_prompt, t
from .storage import SessionStore
from .theme import available_themes, register_themes
from .tools import Arguments

RIGHT_BUTTON = 3


class PromptInput(TextArea):
    """Multiline chat input that grows with its content."""

    MIN_HEIGHT = 3
    MAX_HEIGHT = 12

    class Submitted(Message):
        """Sent when Enter is pressed without Shift."""

        def __init__(self, prompt: PromptInput, text: str) -> None:
            self.prompt = prompt
            self.text = text
            super().__init__()

        @property
        def control(self) -> PromptInput:
            """Widget that sent the message."""
            return self.prompt

    def on_mount(self) -> None:
        """Set the initial height."""
        self._resize()

    @on(TextArea.Changed)
    def handle_changed(self) -> None:
        """Grow or shrink with the content."""
        self._resize()

    def _resize(self) -> None:
        lines = max(1, self.text.count("\n") + 1)
        self.styles.height = min(self.MAX_HEIGHT, max(self.MIN_HEIGHT, lines + 2))

    @on(events.Key)
    def submit_on_enter(self, event: events.Key) -> None:
        """Submit on Enter; leave Shift+Enter alone so it inserts a newline."""
        if event.key != "enter":
            return
        event.stop()
        event.prevent_default()
        self.post_message(self.Submitted(self, self.text))

    @on(MouseDown)
    async def handle_right_click(self, event: MouseDown) -> None:
        """Paste clipboard text at the cursor instead of copying a selection."""
        if event.button != RIGHT_BUTTON:
            return
        event.stop()
        text = read_text(self.app.clipboard)
        if text:
            self.insert(text)
            self.focus()


class ConfirmScreen(ModalScreen[bool]):
    """Modal dialog asking for a yes/no decision."""

    CSS = """
    ConfirmScreen {
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

    def __init__(
        self,
        question: str,
        language: UILanguage,
        title_key: str = "confirm_title",
    ) -> None:
        super().__init__()
        self.question = question
        self.language = language
        self.title_key = title_key

    def compose(self) -> ComposeResult:
        """Build the question and the two decision buttons."""
        with Vertical(id="confirm-dialog"):
            yield Static(
                f"[bold]{t(self.language, self.title_key)}[/]",
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
    NOTIFICATION_TIMEOUT = 2.0
    CSS = """
    Screen {
        background: $surface;
    }
    #log {
        height: 1fr;
        padding: 1 2;
    }
    .message {
        margin: 0 0 1 0;
        width: 100%;
        min-height: 3;
        content-align: left middle;
    }
    .user {
        background: $footer-background;
        border: none;
        border-left: heavy $primary;
        padding: 1 1;
        color: $text;
    }
    .assistant {
        background: $panel-darken-1;
        border: none;
        padding: 1 1 1 2;
        color: $text;
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
    #textual-toastrack {
        dock: top;
        align: right top;
        margin-top: 1;
        margin-bottom: 0;
    }
    #sidebar {
        dock: right;
        width: 44;
        height: 1fr;
        display: none;
        padding: 1 1;
        background: $panel;
        border-left: vkey $primary;
    }
    #sidebar-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }
    #session-list {
        height: 1fr;
        margin-bottom: 1;
    }
    #session-actions {
        height: auto;
    }
    #session-actions Button {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        conversation: Conversation,
        ui_language: UILanguage = "en",
        reply_language: ReplyLanguage = "auto",
        theme_name: str = "daneel",
        store: SessionStore | None = None,
    ) -> None:
        super().__init__()
        self.conversation = conversation
        self.lang = ui_language
        self.reply_language = reply_language
        self.theme_name = theme_name
        self.store = store or SessionStore(":memory:")
        self.current_session_id: int | None = None
        self._busy = False
        self._welcome: Static | None = None
        self._hints: Static | None = None
        self._transcript: list[str] = []
        self._last_answer: str | None = None
        self._sidebar_mode: str | None = None
        self._session_options: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        """Build the initial widget tree."""
        yield Header()
        with VerticalScroll(id="log"):
            self._welcome = Static(t(self.lang, "welcome"), classes="message")
            yield self._welcome
        with Vertical(id="composer"):
            yield PromptInput(
                placeholder=t(self.lang, "prompt_placeholder"), id="prompt"
            )
            self._hints = Static(t(self.lang, "hints"), id="hints")
            yield self._hints
        with Vertical(id="sidebar"):
            pass

    def on_mount(self) -> None:
        """Register themes, apply the selected language, and focus the input."""
        register_themes(self)
        self.theme = self.theme_name
        self._apply_language()
        install_confirmation(self.conversation, self.confirm_tool_call)
        self.query_one("#prompt", PromptInput).focus()

    def on_unmount(self) -> None:
        """Close the session database when the app exits."""
        self.store.close()

    async def confirm_tool_call(self, name: str, arguments: Arguments) -> bool:
        """Ask the user in a modal whether the tool call may run."""
        rendered = render_arguments(arguments)
        question = t(
            self.lang, "confirm_tool_question", name=name, arguments=rendered
        )

        async def ask() -> bool:
            return await self.push_screen_wait(
                ConfirmScreen(question, self.lang)
            )

        allowed = await self.run_worker(ask()).wait()
        if not allowed:
            self._toast(t(self.lang, "tool_denied", name=name), severity="warning")
        return allowed

    def _apply_language(self) -> None:
        """Update language-dependent widgets and key bindings."""
        if self._welcome is not None:
            self._welcome.update(t(self.lang, "welcome"))
        if self._hints is not None:
            self._hints.update(t(self.lang, "hints"))
        self.query_one("#prompt", PromptInput).placeholder = t(
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

    @on(MouseDown)
    async def handle_right_click(self, event: MouseDown) -> None:
        """Copy the current selection when the right mouse button is pressed.

        The selection has to be read on MouseDown: Textual clears it on the
        MouseUp that precedes the Click event for an in-place click.
        """
        if event.button != RIGHT_BUTTON:
            return
        selected = self.screen.get_selected_text()
        if selected:
            self.copy_to_clipboard(selected)
            self._toast(t(self.lang, "copied"))
        else:
            self._toast(t(self.lang, "nothing_selected"), severity="warning")

    def _toast(self, text: str, severity: SeverityLevel = "information") -> None:
        """Show a short-lived notification instead of a chat log line."""
        self.notify(
            text,
            title=t(self.lang, "notification_title"),
            severity=severity,
        )

    async def _render_history(self, messages: list[ChatMessage]) -> None:
        """Rebuild the visible chat log from stored messages."""
        self.conversation.messages = list(messages)
        self._transcript = []
        self._last_answer = None

        log = self.query_one("#log", VerticalScroll)
        for child in list(log.children):
            await child.remove()
        self._welcome = Static(t(self.lang, "welcome"), classes="message")
        await log.mount(self._welcome)

        for message in messages:
            if message.role == "user":
                await log.mount(
                    Static(escape(message.content), classes="message user")
                )
                self._transcript.append(message.content)
            elif message.role == "assistant" and message.content:
                await log.mount(
                    Static(escape(message.content), classes="message assistant")
                )
                self._transcript.append(message.content)
                self._last_answer = message.content
        log.scroll_end(animate=False)

    def _sidebar_container(self) -> Vertical:
        return self.query_one("#sidebar", Vertical)

    async def _clear_sidebar(self) -> None:
        sidebar = self._sidebar_container()
        for child in list(sidebar.children):
            await child.remove()

    async def _open_help_sidebar(self) -> None:
        """Show command descriptions in the right-hand panel."""
        keys = (
            "help_lang",
            "help_reply",
            "help_theme",
            "help_sessions",
            "help_load_desc",
            "help_new",
            "help_clear",
            "help_copy",
            "help_help",
        )
        await self._clear_sidebar()
        sidebar = self._sidebar_container()
        await sidebar.mount(
            Static(t(self.lang, "sidebar_help_title"), id="sidebar-title")
        )
        await sidebar.mount(Static("\n".join(t(self.lang, key) for key in keys)))
        sidebar.styles.display = "block"
        self._sidebar_mode = "help"

    async def _open_sessions_sidebar(self) -> None:
        """Show stored sessions in the right-hand panel."""
        sessions = self.store.list_sessions(limit=20)
        await self._clear_sidebar()
        sidebar = self._sidebar_container()
        await sidebar.mount(
            Static(t(self.lang, "sidebar_sessions_title"), id="sidebar-title")
        )
        if not sessions:
            await sidebar.mount(Static(t(self.lang, "sessions_empty")))
        else:
            self._session_options = {}
            options: list[Option] = []
            for session in sessions:
                option_id = f"session-{session.id}"
                self._session_options[option_id] = session.id
                options.append(
                    Option(
                        t(
                            self.lang,
                            "session_line",
                            id=session.id,
                            title=session.title,
                            count=session.message_count,
                            date=session.updated_at[:16].replace("T", " "),
                        ),
                        id=option_id,
                    )
                )
            option_list = OptionList(*options, id="session-list")
            await sidebar.mount(option_list)
            if self.current_session_id is not None:
                current = f"session-{self.current_session_id}"
                if current in self._session_options:
                    option_list.highlighted = list(self._session_options).index(
                        current
                    )
            actions = Vertical(id="session-actions")
            await sidebar.mount(actions)
            await actions.mount(
                Button(t(self.lang, "sidebar_load"), id="session-load", variant="primary")
            )
            await actions.mount(
                Button(t(self.lang, "sidebar_delete"), id="session-delete", variant="error")
            )
            await actions.mount(
                Button(t(self.lang, "sidebar_close"), id="sidebar-close")
            )
        sidebar.styles.display = "block"
        self._sidebar_mode = "sessions"

    def _close_sidebar(self) -> None:
        """Hide the right-hand panel and return focus to the input."""
        self._sidebar_container().styles.display = "none"
        self._sidebar_mode = None
        self._session_options.clear()
        self.query_one("#prompt", PromptInput).focus()

    def _highlighted_session_id(self) -> int | None:
        """Return the id of the highlighted session in the sidebar."""
        option_list = self.query_one("#session-list", OptionList)
        if option_list.highlighted is None:
            return None
        option = option_list.get_option_at_index(option_list.highlighted)
        return self._session_options.get(option.id or "")

    async def _load_session(self, session_id: int) -> bool:
        """Load a stored session into the conversation and chat log."""
        if self.store.get_session(session_id) is None:
            self._toast(
                t(self.lang, "session_not_found", id=session_id),
                severity="warning",
            )
            return False
        self.current_session_id = session_id
        await self._render_history(self.store.load_messages(session_id))
        self._toast(t(self.lang, "session_loaded", id=session_id))
        return True

    async def _delete_session(self, session_id: int) -> None:
        """Ask for confirmation, then remove a stored session."""
        session = self.store.get_session(session_id)
        if session is None:
            self._toast(
                t(self.lang, "session_not_found", id=session_id),
                severity="warning",
            )
            return
        question = t(
            self.lang,
            "confirm_delete_question",
            id=session.id,
            title=session.title,
        )

        async def ask() -> bool:
            return await self.push_screen_wait(
                ConfirmScreen(question, self.lang, "confirm_delete_title")
            )

        if not await self.run_worker(ask()).wait():
            return
        self.store.delete_session(session_id)
        if self.current_session_id == session_id:
            await self.action_clear()
        self._toast(t(self.lang, "session_deleted", id=session_id))
        if self._sidebar_mode == "sessions":
            await self._open_sessions_sidebar()

    @on(events.Key)
    def close_sidebar_on_escape(self, event: events.Key) -> None:
        """Close the sidebar with Escape."""
        if event.key == "escape" and self._sidebar_mode:
            event.stop()
            self._close_sidebar()

    @on(Button.Pressed, "#sidebar-close")
    def close_sidebar_button(self) -> None:
        """Close the sidebar with its button."""
        self._close_sidebar()

    @on(OptionList.OptionSelected, "#session-list")
    async def select_session(self, event: OptionList.OptionSelected) -> None:
        """Load the session chosen with the mouse or keyboard."""
        if event.option_id:
            await self._load_session(self._session_options[event.option_id])

    @on(Button.Pressed, "#session-load")
    async def load_session_button(self) -> None:
        """Load the highlighted session."""
        session_id = self._highlighted_session_id()
        if session_id is None:
            self._toast(t(self.lang, "session_none_selected"), severity="warning")
            return
        await self._load_session(session_id)

    @on(Button.Pressed, "#session-delete")
    async def delete_session_button(self) -> None:
        """Delete the highlighted session after confirmation."""
        session_id = self._highlighted_session_id()
        if session_id is None:
            self._toast(t(self.lang, "session_none_selected"), severity="warning")
            return
        await self._delete_session(session_id)

    @on(PromptInput.Submitted, "#prompt")
    async def handle_submit(self, event: PromptInput.Submitted) -> None:
        """Handle either a local command or a message for the agent."""
        if self._busy:
            return
        text = event.text.strip()
        if not text:
            return
        event.prompt.clear()
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
                self._toast(
                    t(self.lang, "lang_changed", language=argument.upper())
                )
            else:
                self._toast(t(self.lang, "usage_lang"), severity="warning")
        elif name == "reply":
            if argument in {"auto", "en", "ru"}:
                self.reply_language = cast(ReplyLanguage, argument)
                self.conversation.client.system_prompt = build_system_prompt(argument)
                self._toast(
                    t(self.lang, "reply_changed", language=argument.upper())
                )
            else:
                self._toast(t(self.lang, "usage_reply"), severity="warning")
        elif name == "theme":
            if not argument:
                self._toast(
                    t(self.lang, "theme_list", themes=", ".join(available_themes()))
                )
            elif argument in available_themes():
                self.theme_name = argument
                self.theme = argument
                self._toast(t(self.lang, "theme_changed", theme=argument))
            else:
                self._toast(
                    t(self.lang, "theme_unknown", theme=argument),
                    severity="warning",
                )
        elif name == "sessions":
            await self._open_sessions_sidebar()
        elif name == "load":
            try:
                session_id = int(argument)
            except ValueError:
                self._toast(t(self.lang, "usage_load"), severity="warning")
            else:
                await self._load_session(session_id)
        elif name == "new":
            await self.action_clear()
            self.current_session_id = None
            self._toast(t(self.lang, "session_new"))
        elif name == "copy":
            if argument not in ("", "last"):
                self._toast(t(self.lang, "usage_copy"), severity="warning")
            elif not self._transcript:
                self._toast(t(self.lang, "nothing_to_copy"), severity="warning")
            elif argument == "last":
                if self._last_answer is None:
                    self._toast(t(self.lang, "nothing_to_copy"), severity="warning")
                else:
                    self.copy_to_clipboard(self._last_answer)
                    self._toast(t(self.lang, "copied"))
            else:
                self.copy_to_clipboard("\n".join(self._transcript))
                self._toast(t(self.lang, "copied"))
        elif name == "clear":
            await self.action_clear()
        elif name == "help":
            await self._open_help_sidebar()
        else:
            self._toast(
                t(self.lang, "unknown_command", command=name), severity="warning"
            )

    async def send(self, text: str) -> None:
        """Send a message and render the streaming answer."""
        prompt = self.query_one("#prompt", PromptInput)
        log = self.query_one("#log", VerticalScroll)
        self._busy = True
        prompt.disabled = True
        self.sub_title = t(self.lang, "thinking")
        start_len = len(self.conversation.messages)

        await log.mount(Static(escape(text), classes="message user"))
        self._transcript.append(text)
        answer = Static("", classes="message assistant")
        await log.mount(answer)

        received = ""
        try:
            async for chunk in self.conversation.stream_answer(text):
                received += chunk
                answer.update(escape(received))
                log.scroll_end(animate=False)
        except OllamaError as exc:
            message = t(self.lang, exc.message_key, detail=exc.detail)
            self._transcript.append(f"{t(self.lang, 'error_prefix')}: {message}")
            answer.update(
                f"[bold red]{t(self.lang, 'error_prefix')}:[/] {escape(message)}"
            )
            answer.set_class(True, "error")
        else:
            self._transcript.append(received)
            self._last_answer = received
            if self.current_session_id is None:
                self.current_session_id = self.store.create_session(
                    text.replace("\n", " ")[:40],
                    model=self.conversation.client.model,
                    reply_mode=self.reply_language,
                )
            self.store.append_messages(
                self.current_session_id,
                self.conversation.messages[start_len:],
            )
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
        self._toast(t(self.lang, "lang_changed", language=self.lang.upper()))

    async def action_clear(self) -> None:
        """Clear the conversation and reset the chat log."""
        if self._busy:
            return
        self.conversation.clear()
        self._transcript.clear()
        self._last_answer = None
        self.current_session_id = None
        log = self.query_one("#log", VerticalScroll)
        for child in list(log.children):
            await child.remove()
        self._welcome = Static(t(self.lang, "welcome"), classes="message")
        await log.mount(self._welcome)
