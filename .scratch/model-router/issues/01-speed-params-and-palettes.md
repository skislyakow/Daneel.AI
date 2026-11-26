Status: resolved

# Chunk 1 — параметры скорости и ручное переключение

## Цель

Отправить `think: false`, `options` и `keep_alive` в запросах; добавить `/model`, `/think`, сохранение выбора и отображение модели в статусе.

## Шаги

1. Расширить `Settings` и `Preferences`: `model`, `think`, `auto_route`, параметры запроса.
2. Обновить `OllamaClient` и `from_settings`: payload содержит `think`, `options`, `keep_alive`.
3. Добавить команды `/model` (choices из `/api/tags`), `/think on|off`, `/router auto|manual`.
4. Показывать модель в нижней строке вместе с workspace.
5. Тесты payload, preferences и TUI-палитр.

## Критерии готовности

- Обычный запрос уходит с `think: false` и ограниченным `num_ctx`.
- Модель и режим thinking сохраняются между запусками.
- `/model` показывает установленные модели и применяет выбор без перезапуска.
