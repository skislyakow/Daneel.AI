"""Entry point for Daneel.AI: a Textual TUI with a plain-text fallback."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from io import TextIOWrapper
from typing import cast

from daneel.core import Conversation, OllamaClient, OllamaError
from daneel.i18n import (
    UILanguage,
    build_system_prompt,
    resolve_reply_language,
    resolve_ui_language,
    t,
)
from daneel.tui import DaneelApp

# Windows consoles may use cp1251, which cannot encode emoji.
cast(TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
cast(TextIOWrapper, sys.stderr).reconfigure(encoding="utf-8")

EXIT_KEYS = {"exit", "quit", "выход"}


async def run_cli(language: UILanguage, conversation: Conversation) -> None:
    """Run the simple text mode without a full-screen interface."""
    print(t(language, "cli_started"))
    print(t(language, "cli_exit_hint") + "\n")

    while True:
        user_input = input(t(language, "cli_prompt"))
        if user_input.strip().lower() in EXIT_KEYS:
            print(t(language, "cli_goodbye"))
            break
        if not user_input.strip():
            continue

        print(t(language, "cli_answer_prefix"), end="", flush=True)
        try:
            async for chunk in conversation.stream_answer(user_input):
                print(chunk, end="", flush=True)
        except OllamaError as exc:
            detail = t(language, exc.message_key, detail=exc.detail)
            print("\n" + t(language, "cli_error", message=detail), end="")
        print("\n")


def main() -> None:
    """Parse options, build the core objects, and start the chosen interface."""
    parser = argparse.ArgumentParser(description="Daneel.AI — local AI agent")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="use plain text mode instead of the TUI",
    )
    parser.add_argument(
        "--lang",
        choices=("en", "ru"),
        default=None,
        help="interface language (default: en, or DANEEL_LANG)",
    )
    parser.add_argument(
        "--reply",
        choices=("auto", "en", "ru"),
        default=None,
        help="agent reply language: auto follows the user (default: auto)",
    )
    args = parser.parse_args()

    language = resolve_ui_language(args.lang, os.environ.get("DANEEL_LANG"))
    reply_language = resolve_reply_language(args.reply)
    conversation = Conversation(
        OllamaClient(system_prompt=build_system_prompt(reply_language))
    )

    if args.cli:
        asyncio.run(run_cli(language, conversation))
    else:
        DaneelApp(
            conversation,
            ui_language=language,
            reply_language=reply_language,
        ).run()


if __name__ == "__main__":
    main()
