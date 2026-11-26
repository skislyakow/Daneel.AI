Status: resolved

# Выбор модели: параметры скорости, ручное переключение и авто-роутер

## Проблема

Модель `qwen3.5:4b` даёт качественные ответы и поддерживает инструменты, но работает медленно: у неё включён reasoning по умолчанию, большой контекст, а каждый запуск может требовать загрузки модели. Пользователю нужен быстрый отклик в обычном чате и возможность получить «тяжёлый» ответ или инструменты без перезапуска агента.

## Решение

1. Запросы к `/api/chat` отправляются с `think: false`, ограниченным `num_ctx`, `num_predict` и умеренной `temperature`; модель удерживается в памяти через `keep_alive`.
2. Добавляются команды `/model` (палитра установленных моделей из `/api/tags`), `/think on|off` и `/router auto|manual`. Выбор сохраняется в `settings.json`.
3. Авто-роутер на эвристиках выбирает лёгкую модель `qwen2.5:1.5b` для коротких простых сообщений и тяжёлую `qwen3.5:4b` для сложных задач и любых операций с инструментами. Ручной `/model` отключает авто-режим до `/router auto`.
4. Нижняя строка статуса показывает текущую рабочую директорию и активную модель (с пометкой auto/manual).

## Истории пользователей

1. As a user, I want simple questions answered quickly, so that the chat feels responsive.
2. As a user, I want complex questions and tool calls to use the capable model automatically.
3. As a user, I want to switch models manually from a palette without restarting.
4. As a user, I want to toggle reasoning on demand for hard problems.
5. As a user, I want the chosen model and reasoning mode to survive restarts.
6. As a user, I want to see which model is active right now.
7. As a developer, I want routing rules to be deterministic and testable without a model.

## Решения по реализации

- Новый модуль `daneel/router.py` с `ModelRouter.choose(text)`.
- Правила: инструменты/файлы/погода → тяжёлая модель; длинное сообщение, код, слова «проанализируй», «сравни», «подробно» → тяжёлая; иначе лёгкая.
- `Settings` получает `think`, `auto_route` и параметры запроса; `Preferences` сохраняет `model`, `think`, `auto_route`.
- Ollama client отправляет `think`, `options` и `keep_alive` в каждом запросе.
- `/api/tags` используется только для палитры моделей; при недоступности API показывается warning-тост.

## Решения по тестированию

- Юнит-тесты роутера на таблице примеров.
- Тесты payload: `think`, `options`, `keep_alive`.
- Тесты персистентности `model`/`think`/`auto_route`.
- TUI-тесты `/model`, `/think`, `/router` через `run_test()` с моком `/api/tags`.

## Вне скоупа

- Вызов LLM для классификации сложности (добавляет задержку).
- Автоматическая загрузка отсутствующих моделей.
- Маршрутизация между будущими агентами `Daneel_Router`/воркерами.

## Дополнительные заметки

Роутер — дешёвый эвристический слой, а не мультиагентная система. Он решает только «лёгкая или тяжёлая модель» для текущего сообщения.
