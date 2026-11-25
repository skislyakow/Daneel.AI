"""Terminal interface for Daneel.AI, built with Textual."""

from __future__ import annotations

from typing import cast

from rich.markup import escape
from rich.style import Style as RichStyle
from rich.text import Text
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
from .commands import COMMANDS, Command, MenuEntry, command_named, matching_commands
from .config import PreferencesStore
from .confirmation import install_confirmation, render_arguments
from .core import Conversation, Message as ChatMessage, OllamaError
from .i18n import ReplyLanguage, UILanguage, build_system_prompt, t
from .storage import SessionStore
from .theme import available_themes, register_themes
from .tools import Arguments

RIGHT_BUTTON = 3
DELETE_ICON = "✕"


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
    async def handle_keys(self, event: events.Key) -> None:
        """Navigate the menu, or submit the input when no menu is active."""
        app = self.app
        if event.key in ("up", "down") and getattr(app, "has_suggestions", False):
            event.stop()
            event.prevent_default()
            app.move_suggestion(1 if event.key == "down" else -1)
            return
        if event.key == "escape" and getattr(app, "has_suggestions", False):
            event.stop()
            event.prevent_default()
            app.hide_suggestions()
            return
        if event.key == "delete":
            delete = getattr(app, "delete_highlighted_session", None)
            if callable(delete):
                event.stop()
                event.prevent_default()
                await delete()
                return
        if event.key != "enter":
            return
        event.stop()
        event.prevent_default()
        activate = getattr(app, "activate_suggestion", None)
        if callable(activate) and await activate():
            return
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
    #suggestions {
        display: none;
        height: auto;
        max-height: 8;
        margin: 0 2;
        background: $panel;
        border: none;
        border-left: vkey $menu-edge;
        border-right: vkey $menu-edge;
    }
    #hints {
        height: 3;
        margin: 1 2 1 2;
        padding: 0 1;
        border: none;
        border-left: vkey $menu-edge;
        border-right: vkey $menu-edge;
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
    """

    def __init__(
        self,
        conversation: Conversation,
        ui_language: UILanguage = "en",
        reply_language: ReplyLanguage = "auto",
        theme_name: str = "daneel",
        store: SessionStore | None = None,
        preferences: PreferencesStore | None = None,
    ) -> None:
        super().__init__()
        self.conversation = conversation
        self.lang = ui_language
        self.reply_language = reply_language
        self.theme_name = theme_name
        self.store = store or SessionStore(":memory:")
        self.preferences = preferences
        self.current_session_id: int | None = None
        self._busy = False
        self._welcome: Static | None = None
        self._hints: Static | None = None
        self._transcript: list[str] = []
        self._last_answer: str | None = None
        self._suggestions: list[Command] = []
        self._choices: list[MenuEntry] = []
        self._active_command: Command | None = None

    def compose(self) -> ComposeResult:
        """Build the initial widget tree."""
        yield Header()
        with VerticalScroll(id="log"):
            self._welcome = Static(t(self.lang, "welcome"), classes="message")
            yield self._welcome
        with Vertical(id="composer"):
            yield OptionList(id="suggestions")
            yield PromptInput(
                placeholder=t(self.lang, "prompt_placeholder"), id="prompt"
            )
            self._hints = Static(t(self.lang, "hints"), id="hints")
            yield self._hints

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Provide a soft edge color for themes without a custom one."""
        color = "#3C5368" if self.current_theme.dark else "#B6C7D6"
        return {"menu-edge": color}

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
        self._update_suggestions(
            self.query_one("#prompt", PromptInput).text
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

    def _remember(self, **changes: str) -> None:
        """Persist a preference changed from the interface."""
        if self.preferences is not None:
            self.preferences.update(**changes)

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

    @property
    def has_suggestions(self) -> bool:
        """Whether the command or argument menu is currently active."""
        return bool(self._suggestions or self._choices)

    def _suggestion_list(self) -> OptionList:
        return self.query_one("#suggestions", OptionList)

    @staticmethod
    def _two_columns(left: str, right: str, width: int) -> Text:
        """Render a bright label and a dim description as aligned columns."""
        return Text.assemble(
            (left, "bold"),
            " " * (width - len(left) + 2),
            (right, "dim"),
        )

    def _render_menu(self, rows: list[tuple[str, str, str, str | None]]) -> None:
        """Display aligned rows with an optional delete icon on the right."""
        width = max((len(label) for _, label, _, _ in rows), default=0)
        option_list = self._suggestion_list()
        content_width = max(
            option_list.size.width - 2,
            width + max((len(description) + 4 for _, _, description, _ in rows), default=0),
        )
        options: list[Option] = []
        for option_id, label, description, delete_id in rows:
            prompt = self._two_columns(label, description, width)
            if delete_id is not None:
                prompt.append(" " * max(1, content_width - len(prompt.plain) - 1))
                prompt.append(
                    DELETE_ICON,
                    RichStyle(
                        color=self.current_theme.error, meta={"delete": delete_id}
                    ),
                )
            options.append(Option(prompt, id=option_id))
        option_list.set_options(options)
        option_list.highlighted = 0 if rows else None
        option_list.styles.display = "block"

    def _command_rows(self) -> list[tuple[str, str, str, str | None]]:
        """Build the two-column command list shown when `/` is typed."""
        width = max(len(f"/{command.name}") for command in COMMANDS)
        return [
            (
                f"cmd-{command.name}",
                f"/{command.name}",
                t(self.lang, command.description_key),
                None,
            )
            for command in COMMANDS
        ]

    def show_menu(self, name: str) -> None:
        """Open a command's argument list."""
        command = command_named(name)
        if command is None:
            return
        prompt = self.query_one("#prompt", PromptInput)
        if command.choices == "sessions" and not self.store.list_sessions(limit=20):
            prompt.clear()
            self._toast(t(self.lang, "sessions_empty"), severity="warning")
            return
        self._suggestions = []
        self._active_command = command
        prompt.clear()
        prompt.insert(command.insert_text)
        prompt.cursor_location = (0, len(command.insert_text))
        self._update_suggestions(prompt.text)

    def _resolve_choices(self, command: Command) -> list[MenuEntry]:
        """Resolve fixed, theme, or session choices for an active command."""
        if command.choices == "themes":
            return [MenuEntry(name, name) for name in available_themes()]
        if command.choices == "sessions":
            return [
                MenuEntry(str(session.id), f"#{session.id} {session.title}")
                for session in self.store.list_sessions(limit=20)
            ]
        return [
            MenuEntry(choice.value, t(self.lang, choice.label_key))
            for choice in (command.choices or ())
        ]

    def _hide_suggestions(self) -> None:
        if not self.has_suggestions:
            return
        self._suggestions = []
        self._choices = []
        self._active_command = None
        option_list = self._suggestion_list()
        option_list.styles.display = "none"
        option_list.clear_options()

    def hide_suggestions(self) -> None:
        """Public wrapper used by the input widget."""
        self._hide_suggestions()

    def _update_suggestions(self, text: str) -> None:
        """Show command names or filter the choices of the active command."""
        if self._active_command is not None:
            query = text.partition(" ")[2].lower()
            matches = [
                entry
                for entry in self._resolve_choices(self._active_command)
                if query in f"{entry.value} {entry.label}".lower()
            ]
            self._choices = matches
            option_list = self._suggestion_list()
            if matches:
                delete_ids = self._active_command.choices == "sessions"
                self._render_menu(
                    [
                        (
                            f"choice-{entry.value}",
                            entry.value,
                            entry.label,
                            entry.value if delete_ids else None,
                        )
                        for entry in matches
                    ]
                )
            else:
                option_list.styles.display = "none"
                option_list.clear_options()
            return
        if not text.startswith("/") or " " in text:
            self._hide_suggestions()
            return
        matches = matching_commands(text)
        if not matches:
            self._hide_suggestions()
            return
        self._suggestions = matches
        self._render_menu(
            [
                (
                    f"cmd-{command.name}",
                    f"/{command.name}",
                    t(self.lang, command.description_key),
                    None,
                )
                for command in matches
            ]
        )

    def move_suggestion(self, delta: int) -> None:
        """Move the highlighted row, wrapping around."""
        count = len(self._choices) if self._active_command else len(self._suggestions)
        if not count:
            return
        option_list = self._suggestion_list()
        current = option_list.highlighted or 0
        option_list.highlighted = (current + delta) % count

    async def activate_suggestion(self) -> bool:
        """Apply the highlighted choice, or open the highlighted command."""
        if self._active_command is not None:
            return await self.apply_choice()
        if not self._suggestions:
            return False
        option_list = self._suggestion_list()
        command = self._suggestions[option_list.highlighted or 0]
        prompt = self.query_one("#prompt", PromptInput)
        if command.choices is None:
            self._hide_suggestions()
            prompt.clear()
            await self.handle_command(f"/{command.name}")
            return True
        self._suggestions = []
        self._active_command = command
        prompt.clear()
        prompt.insert(command.insert_text)
        prompt.cursor_location = (0, len(command.insert_text))
        self._update_suggestions(prompt.text)
        return True

    async def apply_choice(self) -> bool:
        """Apply the highlighted argument immediately and close the menu."""
        if self._active_command is None or not self._choices:
            return False
        option_list = self._suggestion_list()
        entry = self._choices[option_list.highlighted or 0]
        command = self._active_command
        self._hide_suggestions()
        self.query_one("#prompt", PromptInput).clear()
        if command.name == "sessions":
            await self._load_session(int(entry.value))
        else:
            await self.handle_command(f"/{command.name} {entry.value}")
        return True

    @on(TextArea.Changed, "#prompt")
    def prompt_changed(self, event: TextArea.Changed) -> None:
        """Keep the popup in sync with the input."""
        self._update_suggestions(self.query_one("#prompt", PromptInput).text)

    @on(OptionList.OptionSelected, "#suggestions")
    async def suggestion_selected(self) -> None:
        """Activate a command or argument picked with the mouse."""
        await self.activate_suggestion()

    async def delete_highlighted_session(self) -> bool:
        """Delete the session highlighted in the palette, if any."""
        if (
            self._active_command is None
            or self._active_command.choices != "sessions"
            or not self._choices
        ):
            return False
        highlighted = self._suggestion_list().highlighted or 0
        await self._delete_session(int(self._choices[highlighted].value))
        return True

    @on(events.MouseDown, "#suggestions")
    def delete_session_icon(self, event: events.MouseDown) -> None:
        """Handle a click on the delete icon shown next to a session."""
        session_id = event.style.meta.get("delete")
        if session_id is None:
            return
        event.stop()
        self.run_worker(self._delete_session(int(session_id)))

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
        prompt = self.query_one("#prompt", PromptInput)
        prompt.focus()
        if self._active_command is not None:
            self._update_suggestions(prompt.text)

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
                self._remember(ui_language=argument)
                self._toast(
                    t(self.lang, "lang_changed", language=argument.upper())
                )
            else:
                self._toast(t(self.lang, "usage_lang"), severity="warning")
        elif name == "reply":
            if argument in {"auto", "en", "ru"}:
                self.reply_language = cast(ReplyLanguage, argument)
                self.conversation.client.system_prompt = build_system_prompt(argument)
                self._remember(reply_language=argument)
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
                self._remember(theme=argument)
                self._toast(t(self.lang, "theme_changed", theme=argument))
            else:
                self._toast(
                    t(self.lang, "theme_unknown", theme=argument),
                    severity="warning",
                )
        elif name == "sessions":
            self.show_menu("sessions")
        elif name == "new":
            await self.action_clear()
            self.current_session_id = None
            self._toast(t(self.lang, "session_new"))
        elif name == "copy":
            if argument == "all":
                argument = ""
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
        self._remember(ui_language=self.lang)
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
