"""Localization of the Daneel.AI interface and agent reply language."""

from __future__ import annotations

import os
from typing import Final, Literal, cast

UILanguage = Literal["en", "ru"]
ReplyLanguage = Literal["auto", "en", "ru"]

DEFAULT_UI_LANGUAGE: Final[UILanguage] = "en"
DEFAULT_REPLY_LANGUAGE: Final[ReplyLanguage] = "auto"

BASE_SYSTEM_PROMPT: Final = (
    "You are R. Daneel Olivaw (Daneel.AI), a local AI agent named after "
    "Isaac Asimov's robot detective. Your goal is to help the user with "
    "household and work tasks. Be concise, clear, and to the point."
)

REPLY_INSTRUCTIONS: Final[dict[ReplyLanguage, str]] = {
    "auto": "Reply in the same language as the user's message.",
    "en": "Reply in English.",
    "ru": "Reply in Russian.",
}

STRINGS: Final[dict[UILanguage, dict[str, str]]] = {
    "en": {
        "welcome": (
            "🤖 [bold cyan]Daneel.AI[/] — local agent, running offline.\n"
            "[dim]Type a message and press Enter. Ctrl+L clears the chat, "
            "Ctrl+T switches the interface language, Ctrl+C exits.[/]"
        ),
        "prompt_placeholder": "Message... (Enter to send)",
        "you": "You",
        "daneel": "Daneel",
        "thinking": "thinking…",
        "error_prefix": "Error",
        "connection_error": "Could not connect to Ollama. Check that the service is running.",
        "http_error": "Ollama returned an error: {detail}",
        "clear_binding": "Clear",
        "toggle_binding": "Language",
        "quit_binding": "Quit",
        "cli_started": "🤖 Daneel.AI is running offline.",
        "cli_exit_hint": "(Type 'exit' or 'quit' to leave)",
        "cli_goodbye": "🤖 Goodbye, creator.",
        "cli_prompt": "You: ",
        "cli_answer_prefix": "🤖 Daneel: ",
        "cli_error": "Error: {message}",
        "note": "System",
        "unknown_command": "Unknown command: {command}. Type /help for the list.",
        "usage_lang": "Usage: /lang en|ru",
        "usage_reply": "Usage: /reply auto|en|ru",
        "help_text": "Commands: /lang en|ru, /reply auto|en|ru, /clear, /help",
        "lang_changed": "Interface language: {language}",
        "reply_changed": "Agent replies: {language}",
        "language_en": "English",
        "language_ru": "Russian",
        "reply_auto": "same as your message",
    },
    "ru": {
        "welcome": (
            "🤖 [bold cyan]Daneel.AI[/] — локальный агент, работает офлайн.\n"
            "[dim]Введите сообщение и нажмите Enter. Ctrl+L очищает диалог, "
            "Ctrl+T переключает язык интерфейса, Ctrl+C — выход.[/]"
        ),
        "prompt_placeholder": "Сообщение... (Enter — отправить)",
        "you": "Вы",
        "daneel": "Даниел",
        "thinking": "думает…",
        "error_prefix": "Ошибка",
        "connection_error": "Не удалось подключиться к Ollama. Проверьте, запущен ли сервис.",
        "http_error": "Ollama вернул ошибку: {detail}",
        "clear_binding": "Очистить",
        "toggle_binding": "Язык",
        "quit_binding": "Выход",
        "cli_started": "🤖 Daneel.AI запущен и готов к работе offline.",
        "cli_exit_hint": "(Для выхода введите 'exit', 'quit' или 'выход')",
        "cli_goodbye": "🤖 До встречи, создатель.",
        "cli_prompt": "Вы: ",
        "cli_answer_prefix": "🤖 Даниел: ",
        "cli_error": "Ошибка: {message}",
        "note": "Система",
        "unknown_command": "Неизвестная команда: {command}. Введите /help для списка.",
        "usage_lang": "Использование: /lang en|ru",
        "usage_reply": "Использование: /reply auto|en|ru",
        "help_text": "Команды: /lang en|ru, /reply auto|en|ru, /clear, /help",
        "lang_changed": "Язык интерфейса: {language}",
        "reply_changed": "Язык ответов агента: {language}",
        "language_en": "английский",
        "language_ru": "русский",
        "reply_auto": "как в вашем сообщении",
    },
}


def t(lang: UILanguage, key: str, **values: object) -> str:
    """Return a localized string, substituting any named placeholders."""
    return STRINGS[lang][key].format(**values)


def build_system_prompt(reply_language: ReplyLanguage) -> str:
    """Build the system prompt with the desired reply-language instruction."""
    return f"{BASE_SYSTEM_PROMPT} {REPLY_INSTRUCTIONS[reply_language]}"


def resolve_ui_language(argument: str | None = None, env: str | None = None) -> UILanguage:
    """Resolve the interface language from a CLI argument, env var, or default."""
    value = (argument or env or DEFAULT_UI_LANGUAGE).lower()
    if value in ("en", "ru"):
        return cast(UILanguage, value)
    return DEFAULT_UI_LANGUAGE


def resolve_reply_language(argument: str | None = None) -> ReplyLanguage:
    """Resolve the agent reply mode from a CLI argument or default."""
    value = (argument or DEFAULT_REPLY_LANGUAGE).lower()
    if value in ("auto", "en", "ru"):
        return cast(ReplyLanguage, value)
    return DEFAULT_REPLY_LANGUAGE


def ui_language_from_env() -> str | None:
    """Read the DANEEL_LANG environment variable."""
    return os.environ.get("DANEEL_LANG")
