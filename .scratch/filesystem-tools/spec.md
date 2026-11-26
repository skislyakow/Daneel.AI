Status: resolved

# Инструменты работы с файлами в границах рабочей директории

## Проблема

Агент умеет вызывать инструменты и подтверждать их в обеих оболочках, но пока единственный инструмент — погода. Переменная `DANEEL_WORKSPACE` объявлена границей для будущих файловых операций, но нигде не используется. Пользователю нужно, чтобы агент мог безопасно отвечать на вопросы о содержимом рабочей директории, не выходя за её пределы.

## Решение

Добавить два инструмента только для чтения: `list_directory` и `read_file`. Они включаются по явному opt-in `DANEEL_ENABLE_FS_TOOLS=1`, получают корень из `DANEEL_WORKSPACE`, резолвят каждый путь через `Path.resolve()` и отклоняют любой выход за границу. Каждый вызов требует подтверждения через существующий механизм `ToolRegistry.call()`. Пределы: число записей в листинге и размер читаемого файла.

## Истории пользователей

1. As a user, I want the agent to list files in my workspace, so that I can ask what is in a project.
2. As a user, I want the agent to read a text file from my workspace, so that I can ask questions about its contents.
3. As a user, I want the agent to refuse paths outside the workspace, so that private files are not exposed.
4. As a user, I want every filesystem call confirmed, so that nothing happens silently.
5. As a user, I want filesystem tools disabled by default, so that a new install stays minimal.
6. As a developer, I want the tools testable through the registry with a temporary workspace.

## Решения по реализации

- Новый модуль `daneel/tools/filesystem.py` с фабрикой `create_filesystem_tools(workspace, ...)`.
- Инструменты возвращают читаемые строки-результаты, а не бросают исключения: «path outside workspace», «file too large», «not found» и т.п.
- Оба инструмента имеют `requires_confirmation=False`: по решению пользователя встроенные операции выполняются без окна подтверждения. Реестр по-прежнему поддерживает обязательное подтверждение для будущих инструментов.
- `Settings` получает поле `enable_fs_tools` из окружения; `main.py` регистрирует инструменты при включении.
- Запись, удаление, переименование и запуск команд остаются вне скоупа.

## Решения по тестированию

- Тесты через `ToolRegistry.call()` с подтверждением и без него, на `tmp_path` как workspace.
- Проверки: листинг, чтение, отказ на `..`, отказ на абсолютный путь вне workspace, лимит размера, отказ без подтверждения.
- TUI-тест подтверждения через существующий `run_test()`.

## Вне скоупа

- Изменение файлов, создание/удаление каталогов.
- Поиск по содержимому и FTS.
- Автоматическое включение инструментов.
- Изменение системного промпта и языковых правил.

## Дополнительные заметки

Инструменты не требуют новых зависимостей. Палитра аргументов TUI не меняется: аргументы приходят от модели, а пользователь видит их в диалоге подтверждения.
