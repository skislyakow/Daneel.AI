"""Localization of the Daneel.AI interface and agent reply language."""

from __future__ import annotations

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
        "thinking": "Thinking",
        "thinking_elapsed": "{spinner} Thinking · {duration}",
        "thinking_summary": "● Thought · {duration}",
        "workspace": "Workspace: {path}",
        "error_prefix": "Error",
        "connection_error": "Could not connect to Ollama. Check that the service is running.",
        "http_error": "Ollama returned an error: {detail}",
        "tool_round_limit": (
            "Tool-call limit reached after {detail} rounds. Try a simpler request."
        ),
        "clear_binding": "Clear",
        "toggle_binding": "Language",
        "quit_binding": "Quit",
        "cli_started": "🤖 Daneel.AI is running offline.",
        "cli_exit_hint": "(Type 'exit' or 'quit' to leave)",
        "cli_goodbye": "🤖 Goodbye, creator.",
        "cli_prompt": "You: ",
        "cli_answer_prefix": "🤖 Daneel: ",
        "cli_confirm_prompt": "Allow tool {name} with {arguments}? [Y/n] ",
        "tool_denied": "Tool call denied: {name}",
        "cli_error": "Error: {message}",
        "note": "System",
        "notification_title": "Daneel.AI",
        "copied": "Copied to clipboard.",
        "nothing_selected": "Nothing selected.",
        "confirm_title": "Tool call",
        "confirm_tool_question": "Allow {name} with {arguments}?",
        "confirm_allow": "Allow",
        "confirm_deny": "Deny",
        "unknown_command": "Unknown command: {command}. Type / for the list.",
        "usage_lang": "Usage: /lang en|ru",
        "usage_reply": "Usage: /reply auto|en|ru",
        "usage_theme": "Usage: /theme <name> (or /theme to list)",
        "usage_copy": "Usage: /copy [all|last]",
        "nothing_to_copy": "Nothing to copy.",
        "lang_changed": "Interface language: {language}",
        "reply_changed": "Agent replies: {language}",
        "theme_changed": "Theme: {theme}",
        "theme_list": "Themes: {themes}",
        "theme_unknown": "Unknown theme: {theme}",
        "sessions_empty": "No saved sessions.",
        "sessions_header": "Sessions:",
        "sessions_more": "…and {count} more",
        "session_loaded": "Loaded session #{id}.",
        "session_not_found": "Session #{id} not found.",
        "session_new": "New session started.",
        "session_deleted": "Session #{id} deleted.",
        "help_lang": "switch interface language",
        "help_reply": "agent reply language",
        "help_theme": "change theme",
        "help_sessions": "open the session list",
        "help_new": "start a new session",
        "help_clear": "clear the chat",
        "help_copy": "copy chat or last answer",
        "confirm_delete_title": "Delete session",
        "confirm_delete_question": "Delete session #{id} ({title})?",
        "language_en": "English",
        "language_ru": "Russian",
        "reply_auto": "same as your message",
        "reply_en": "English replies",
        "reply_ru": "Russian replies",
        "copy_all": "whole chat",
        "copy_last": "last answer only",
    },
    "ru": {
        "welcome": (
            "🤖 [bold cyan]Daneel.AI[/] — локальный агент, работает офлайн.\n"
            "[dim]Введите сообщение и нажмите Enter. Ctrl+L/Д очищает диалог, "
            "Ctrl+T/Е переключает язык интерфейса, Ctrl+C/С — выход.[/]"
        ),
        "prompt_placeholder": "Сообщение... (Enter — отправить)",
        "thinking": "Думаю",
        "thinking_elapsed": "{spinner} Думаю · {duration}",
        "thinking_summary": "● Думал · {duration}",
        "workspace": "Рабочая директория: {path}",
        "error_prefix": "Ошибка",
        "connection_error": "Не удалось подключиться к Ollama. Проверьте, запущен ли сервис.",
        "http_error": "Ollama вернул ошибку: {detail}",
        "tool_round_limit": (
            "Лимит вызовов инструментов исчерпан после {detail} раундов. "
            "Попробуйте упростить запрос."
        ),
        "clear_binding": "Очистить",
        "toggle_binding": "Язык",
        "quit_binding": "Выход",
        "cli_started": "🤖 Daneel.AI запущен и готов к работе offline.",
        "cli_exit_hint": "(Для выхода введите 'exit', 'quit' или 'выход')",
        "cli_goodbye": "🤖 До встречи, создатель.",
        "cli_prompt": "Вы: ",
        "cli_answer_prefix": "🤖 Даниел: ",
        "cli_confirm_prompt": (
            "Разрешить инструмент {name} с аргументами {arguments}? [Д/н] "
        ),
        "tool_denied": "Вызов инструмента отклонён: {name}",
        "cli_error": "Ошибка: {message}",
        "note": "Система",
        "notification_title": "Daneel.AI",
        "copied": "Скопировано в буфер обмена.",
        "nothing_selected": "Ничего не выделено.",
        "confirm_title": "Вызов инструмента",
        "confirm_tool_question": "Разрешить {name} с аргументами {arguments}?",
        "confirm_allow": "Разрешить",
        "confirm_deny": "Запретить",
        "unknown_command": "Неизвестная команда: {command}. Введите / для списка.",
        "usage_lang": "Использование: /lang en|ru",
        "usage_reply": "Использование: /reply auto|en|ru",
        "usage_theme": "Использование: /theme <имя> (или /theme для списка)",
        "usage_copy": "Использование: /copy [all|last]",
        "nothing_to_copy": "Нечего копировать.",
        "lang_changed": "Язык интерфейса: {language}",
        "reply_changed": "Язык ответов агента: {language}",
        "theme_changed": "Тема: {theme}",
        "theme_list": "Темы: {themes}",
        "theme_unknown": "Неизвестная тема: {theme}",
        "sessions_empty": "Сохранённых сессий нет.",
        "sessions_header": "Сессии:",
        "sessions_more": "…и ещё {count}",
        "session_loaded": "Загружена сессия #{id}.",
        "session_not_found": "Сессия #{id} не найдена.",
        "session_new": "Начата новая сессия.",
        "session_deleted": "Сессия #{id} удалена.",
        "help_lang": "язык интерфейса",
        "help_reply": "язык ответов агента",
        "help_theme": "сменить тему",
        "help_sessions": "открыть список сессий",
        "help_new": "начать новую сессию",
        "help_clear": "очистить чат",
        "help_copy": "скопировать чат или последний ответ",
        "confirm_delete_title": "Удаление сессии",
        "confirm_delete_question": "Удалить сессию #{id} ({title})?",
        "language_en": "английский",
        "language_ru": "русский",
        "reply_auto": "как в вашем сообщении",
        "reply_en": "ответы на английском",
        "reply_ru": "ответы на русском",
        "copy_all": "весь диалог",
        "copy_last": "только последний ответ",
    },
}


def t(lang: UILanguage, key: str, **values: object) -> str:
    """Return a localized string, substituting any named placeholders."""
    return STRINGS[lang][key].format(**values)


def format_duration(ms: int) -> str:
    """Format elapsed time as seconds, or minutes:seconds when over a minute."""
    total_seconds = max(0, ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}" if minutes else f"{seconds}s"


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
