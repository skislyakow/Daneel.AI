## Agent skills

### Issue tracker

Issues и спеки хранятся как markdown в `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `GLOSSARY.md` и `docs/adr/` в корне репозитория. See `docs/agents/domain.md`.

## Commands

- `uv run pytest` — запускать после изменений в `daneel/`.
- `uv run daneel` — TUI; `uv run daneel --cli` — простой текстовый режим.

## Architecture

- Интерфейс живёт в `daneel/tui.py`, логика Ollama и история — в `daneel/core.py`. Не переноси HTTP-код в TUI.
- Ответы Ollama потоковые (`stream: true`); новые адаптеры должны потреблять `Conversation.stream_answer()`.
