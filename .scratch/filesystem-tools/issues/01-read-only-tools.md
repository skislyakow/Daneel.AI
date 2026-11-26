Status: resolved

# Chunk 1 — инструменты чтения и граница workspace

## Цель

Реализовать `list_directory` и `read_file` в `daneel/tools/filesystem.py`, ограничить пути рабочей директорией и покрыть поведение тестами через реестр.

## Шаги

1. Фабрика `create_filesystem_tools(workspace, *, max_entries=200, max_file_bytes=64_000)`.
2. Резолвинг пути через `Path.resolve()`, проверка `is_relative_to(workspace.resolve())`, отказ на абсолютные пути вне корня.
3. `list_directory`: сортированный список, пометка `dir`/`file`, размер, лимит записей.
4. `read_file`: текстовое чтение с заменой ошибок декодирования, лимит размера.
5. Тесты: `tests/test_filesystem.py` на `tmp_path`, включая отказ без подтверждения.

## Критерии готовности

- Вызов вне workspace возвращает понятное сообщение об отказе.
- Оба инструмента имеют `requires_confirmation=True`.
- `uv run pytest -q` зелёный.
