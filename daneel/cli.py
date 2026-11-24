"""Plain-text interface helpers for confirming tool calls."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .confirmation import render_arguments
from .i18n import UILanguage, t
from .tools import Arguments, Confirm

AFFIRMATIVE = frozenset({"", "y", "yes", "да"})


def _write(text: str) -> None:
    """Print without adding a newline of its own."""
    print(text, end="", flush=True)


def cli_confirmation(
    language: UILanguage,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = _write,
) -> Confirm:
    """Build a confirmation callback that asks in the plain-text interface."""

    async def confirm(name: str, arguments: Arguments) -> bool:
        rendered = render_arguments(arguments)
        prompt = t(
            language, "cli_confirm_prompt", name=name, arguments=rendered
        )
        answer = await asyncio.to_thread(input_fn, prompt)
        if answer.strip().lower() in AFFIRMATIVE:
            return True
        output_fn(t(language, "tool_denied", name=name) + "\n")
        return False

    return confirm
