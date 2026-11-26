Status: resolved

# Подтверждение вызовов инструментов в CLI и TUI

## Проблема

Инструменты agents уже проверяют подтверждение на уровне реестра, но ни один из интерфейсов не предоставляет колбэк подтверждения. Из-за этого любой запрос модели к инструменту отклоняется и пользователь видит только ошибку отказа — в обоих режимах работы невозможно осознанно разрешить операцию. Пользователю нужно понятное место, где видно имя инструмента и его аргументы, и где можно явно согласиться или отказать.

## Решение

Каждый интерфейс предоставляет колбэк подтверждения для разговора с агентом. В текстовом режиме перед выполнением инструмента выводится локализованный запрос с именем инструмента и аргументами; Enter (или `y`/`yes`/`да`) означает согласие, явный отказ (`n`/`no`/`нет`) — запрет. В терминальном интерфейсе показывается модальное окно с теми же данными и кнопками Allow/Deny: Enter подтверждает выбранную кнопку, Esc запрещает. Отказ по-прежнему проходит через существующий путь ошибки отказа, то есть операции никогда не выполняются молча. Новые инструменты по умолчанию не включаются.

## Истории пользователей

1. As a CLI user, I want to see which tool the agent wants to call and with which arguments, so that I can make an informed decision.
2. As a CLI user, I want pressing Enter to approve a tool call, so that I can confirm quickly without extra syntax.
3. As a CLI user, I want to type `n` to reject a tool call, so that I can stop an unwanted operation.
4. As a TUI user, I want a modal dialog listing the tool name and arguments, so that I can review the call without leaving the chat.
5. As a TUI user, I want to choose Allow with Enter and Deny with Esc or `n`, so that the dialog works from the keyboard.
6. As a Russian-speaking user, I want the prompt and buttons in Russian, so that I can understand what I am confirming.
7. As a user, I want a rejected call to be reported as a denial rather than executed, so that I stay in control.
8. As a developer, I want confirmation wired only when the interface has not supplied its own callback, so that injected callbacks in tests and future adapters keep working.
9. As a developer, I want the CLI confirmation logic testable without an interactive terminal, so that the behavior is covered by automated tests.
10. As a developer, I want the TUI dialog testable through the existing interface harness, so that I do not need a human at the keyboard.

## Решения по реализации

- The confirmation callback stays in the core conversation module; interfaces only supply it, and only when no callback was provided explicitly.
- The plain-text interface gets a small confirmation function with injected input and output streams, so the decision can be exercised without a real terminal. Its prompt is localized and shows the tool name plus a readable representation of the arguments.
- The terminal interface gets a modal screen with a localized question, Allow and Deny buttons, keyboard shortcuts for yes/no, and Escape mapped to denial. Enter confirms the focused button, which starts on Allow.
- Denials keep using the existing tool-denial error path and are displayed by the current error rendering in both interfaces.
- Interface strings for prompt, question, buttons, and denial feedback are added to the localization module for both supported languages.
- The system prompt and reply-language rules are not touched.

## Решения по тестированию

A good test observes behavior through a public interface: it presses keys or feeds input, then checks the resulting tool execution or error — never the internal shape of the dialog or callback plumbing.

- Plain-text confirmation: tested through the new injected input/output seam; approve, explicit reject, and empty-input cases.
- Terminal confirmation: tested through the existing application harness by driving the modal with keys and checking whether the tool ran or was denied.
- Tool decision plumbing: tested through the already agreed tool registry and conversation-event seams, including the case where an interface does not override an injected callback.
- Prior art: the existing core, tool, and terminal-interface tests already use a mock HTTP transport, injected clients, and an application harness; follow those patterns.

## Вне скоупа

- Enabling any tool by default or implementing new tools.
- Filesystem operations and the workspace boundary.
- Confirming a whole batch of tool calls at once.
- Changes to the tool-call round limit or tool-call identity handling.
- Glossary, ADRs, and other domain documentation.

## Дополнительные заметки

The two interfaces can be delivered independently: neither depends on the other, and both reuse the same confirmation contract already present in the core.

## Уточнение после реализации

По последующему решению пользователя встроенные инструменты (`get_weather`, `list_directory`, `read_file`) выполняются без подтверждения (`requires_confirmation=False`), чтобы не прерывать работу диалогом. Механизм подтверждения в реестре и обеих оболочках сохранён для будущих инструментов, которым он понадобится.
