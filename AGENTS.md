## Agent skills

### Issue tracker

Задачи и спеки хранятся как markdown в `.scratch/<feature>/`. См. `docs/agents/issue-tracker.md`.

### Domain docs

Один контекст: `GLOSSARY.md` и `docs/adr/` в корне репозитория. См. `docs/agents/domain.md`.

## Команды

- `uv run pytest` — запускать после изменений в `daneel/`.
- `uv run daneel` — TUI; `uv run daneel --cli` — простой текстовый режим.
- `uv run daneel --lang ru --reply ru` — русский интерфейс и русские ответы агента.

## Архитектура

- Интерфейс живёт в `daneel/tui.py`, логика Ollama и история — в `daneel/core.py`. Не переноси HTTP-код в TUI.
- Строки интерфейса, разрешение языка и системный промпт находятся в `daneel/i18n.py`.
- Ответы Ollama потоковые (`stream: true`); новые адаптеры должны потреблять `Conversation.stream_answer()`.
- Код, комментарии и докстринги — на английском; `README.md` — на английском, остальные md-файлы — на русском.
- Язык интерфейса по умолчанию английский, язык ответов — `auto` (ответ на языке сообщения пользователя). Переключение: `/lang`, `/reply`, `Ctrl+T`.
