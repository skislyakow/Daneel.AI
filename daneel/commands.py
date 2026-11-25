"""Registry of slash commands used by the TUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Command:
    """A slash command with its arguments and localized description key."""

    name: str
    args: str
    description_key: str

    @property
    def usage(self) -> str:
        """Full command signature for display."""
        return f"/{self.name} {self.args}".rstrip()

    @property
    def insert_text(self) -> str:
        """Text inserted when the command is accepted."""
        return f"/{self.name} "


COMMANDS: tuple[Command, ...] = (
    Command("lang", "en|ru", "help_lang"),
    Command("reply", "auto|en|ru", "help_reply"),
    Command("theme", "<name>", "help_theme"),
    Command("sessions", "", "help_sessions"),
    Command("load", "<id>", "help_load_desc"),
    Command("new", "", "help_new"),
    Command("clear", "", "help_clear"),
    Command("copy", "[last]", "help_copy"),
    Command("help", "", "help_help"),
)


def matching_commands(prefix: str) -> list[Command]:
    """Return commands whose names start with the typed prefix."""
    value = prefix.lstrip("/").lower()
    return [command for command in COMMANDS if command.name.startswith(value)]
