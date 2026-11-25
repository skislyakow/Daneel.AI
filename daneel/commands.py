"""Registry of slash commands used by the TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChoiceSource = Literal["themes", "sessions"]
"""Dynamic menus resolved by the interface when the command is opened."""


@dataclass(frozen=True, slots=True)
class Choice:
    """A fixed command argument with a localized label."""

    value: str
    label_key: str


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """A resolved choice ready to display and apply."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class Command:
    """A slash command with its arguments and localized description key."""

    name: str
    args: str
    description_key: str
    choices: tuple[Choice, ...] | ChoiceSource | None = None

    @property
    def usage(self) -> str:
        """Full command signature for display."""
        return f"/{self.name} {self.args}".rstrip()

    @property
    def insert_text(self) -> str:
        """Text inserted when the command is accepted."""
        return f"/{self.name} "


COMMANDS: tuple[Command, ...] = (
    Command(
        "lang",
        "en|ru",
        "help_lang",
        (Choice("en", "language_en"), Choice("ru", "language_ru")),
    ),
    Command(
        "reply",
        "auto|en|ru",
        "help_reply",
        (
            Choice("auto", "reply_auto"),
            Choice("en", "reply_en"),
            Choice("ru", "reply_ru"),
        ),
    ),
    Command("theme", "<name>", "help_theme", "themes"),
    Command("sessions", "", "help_sessions", "sessions"),
    Command("new", "", "help_new"),
    Command("clear", "", "help_clear"),
    Command(
        "copy",
        "[all|last]",
        "help_copy",
        (Choice("all", "copy_all"), Choice("last", "copy_last")),
    ),
)


def matching_commands(prefix: str) -> list[Command]:
    """Return commands whose names start with the typed prefix."""
    value = prefix.lstrip("/").lower()
    return [command for command in COMMANDS if command.name.startswith(value)]


def command_named(name: str) -> Command | None:
    """Look up a command by name."""
    return next((command for command in COMMANDS if command.name == name), None)
