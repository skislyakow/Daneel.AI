Status: resolved

# Chunk 2 — opt-in registration и документация

## Цель

Подключить инструменты при `DANEEL_ENABLE_FS_TOOLS=1`, не меняя поведение по умолчанию, и обновить документацию.

## Шаги

1. Добавить `enable_fs_tools` в `Settings`, читать из `DANEEL_ENABLE_FS_TOOLS`.
2. В `main.py` расширить реестр инструментов при включении; базовый реестр — только погода.
3. Обновить README, ARCHITECTURE, AGENTS, CODING_STANDARDS.
4. Убрать из README устаревшие упоминания `/help` и `/load`.

## Критерии готовности

- Без env-флага реестр содержит только `get_weather`.
- С флагом реестр содержит погоду и два файловых инструмента.
- Тесты конфигурации и `uv run pytest -q` зелёные.
