import argparse
import asyncio
import sys
from io import TextIOWrapper
from typing import cast

from daneel.core import Conversation, OllamaClient, OllamaError
from daneel.tui import DaneelApp

# На Windows консоль может использовать cp1251, который не поддерживает эмодзи
cast(TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
cast(TextIOWrapper, sys.stderr).reconfigure(encoding="utf-8")


async def run_cli() -> None:
    """Простой текстовый режим (fallback без полноэкранного интерфейса)."""
    conversation = Conversation(OllamaClient())
    print("🤖 Daneel.AI запущен и готов к работе offline.")
    print("(Для выхода введите 'выход' или 'exit')\n")

    while True:
        user_input = input("Вы: ")
        if user_input.lower() in {"выход", "exit"}:
            print("🤖 До встречи, создатель.")
            break
        if not user_input.strip():
            continue

        print("🤖 Даниел: ", end="", flush=True)
        try:
            async for chunk in conversation.stream_answer(user_input):
                print(chunk, end="", flush=True)
        except OllamaError as exc:
            print(f"\nОшибка: {exc}", end="")
        print("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daneel.AI — локальный ИИ-агент")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="запустить простой текстовый режим вместо TUI",
    )
    args = parser.parse_args()

    if args.cli:
        asyncio.run(run_cli())
    else:
        DaneelApp(Conversation(OllamaClient())).run()


if __name__ == "__main__":
    main()
