# Daneel.AI 🤖

**Daneel.AI** (R. Daneel Olivaw) is a local, autonomous AI agent with an open architecture. The project is built around privacy, offline (on-premise) operation, and gradual expansion to household and work tasks.

## 🎯 MVP goal

Build a minimal working protocol between the user, the agent, and a local LLM, with room to grow into a multi-agent system.

## 🛠️ Stack

* **Language:** Python 3.10+ (development uses 3.12, see `.python-version`)
* **Dependency manager:** [uv](https://docs.astral.sh/uv/)
* **Model runtime:** [Ollama](https://ollama.com)
* **Default model:** `qwen2.5:1.5b` (fast and lightweight for tests) or `llama3.2:3b`
* **HTTP client:** `httpx` (async requests and streaming Ollama responses)
* **Interface:** [Textual](https://textual.textualize.io/) terminal UI
* **Tests:** `pytest` + `pytest-asyncio`

## 🚀 Quick start

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Ollama, then pull a model:
   ```bash
   ollama run qwen2.5:1.5b
   ```
2. Clone the project and install dependencies (uv creates `.venv` and uses the versions from `uv.lock`):
   ```bash
   uv sync
   ```
3. Start the agent (opens the TUI):
   ```bash
   uv run daneel
   ```
   Or run the plain-text mode:
   ```bash
   uv run daneel --cli
   ```

In the TUI: type into the multiline input (it grows with the content), **Enter** sends the whole message, **Shift+Enter** inserts a newline. **Ctrl+L** clears the chat, **Ctrl+T** switches the interface language, **Ctrl+C** exits. Under the Russian keyboard layout, the same physical keys work as **Ctrl+Д**, **Ctrl+Е** and **Ctrl+С**. The localized hint bar at the bottom shows both variants. Typing `/` opens a popup with all commands; it filters as you type. Use **Up/Down** to navigate, **Enter** to insert the highlighted command, then **Enter** again to run it; a mouse click also inserts the command, and **Escape** hides the popup. Local commands: `/lang en|ru`, `/reply auto|en|ru`, `/theme <name>`, `/sessions`, `/load <id>`, `/new`, `/clear`, `/help`. `/help` and `/sessions` open a right-hand sidebar; close it with **Escape** or the Close button.

## 🌍 Run from anywhere

Install the project as a global uv tool from the repository directory:

```bash
uv tool install --editable .
uv tool update-shell        # only if uv's bin directory is not on PATH
```

Then `daneel` is available from any directory:

```bash
daneel
daneel --cli --lang ru --reply ru
```

`--editable` means source changes are picked up without reinstalling. After changing dependencies, re-run `uv tool install --editable --force .` so the tool environment picks up the new packages. Remove the tool with `uv tool uninstall daneel`.

## ⚙️ Configuration

Settings are read from environment variables; CLI flags take precedence.

| Variable | Meaning | Default |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | Ollama API address | `http://localhost:11434` |
| `DANEEL_MODEL` | Model name | `qwen2.5:1.5b` |
| `DANEEL_WORKSPACE` | Root directory for future agent operations | current directory |
| `DANEEL_LANG` | Interface language (`en`/`ru`) | `en` |
| `DANEEL_REPLY` | Reply mode (`auto`/`en`/`ru`) | `auto` |
| `DANEEL_THEME` | Textual theme name | `daneel` |
| `DANEEL_SESSION_DB` | Path to the session SQLite database | platform-specific user data dir |

`DANEEL_WORKSPACE` is the safety boundary for tools that will read or change files. Since the agent can be started from anywhere, do not rely on the current directory for operations.

## 🌐 Languages

The interface is English by default; the agent's reply language is configured independently.

```bash
uv run daneel --lang ru                       # Russian interface
uv run daneel --reply ru                      # agent always replies in Russian
DANEEL_LANG=ru DANEEL_REPLY=ru daneel --cli  # language via environment
```

* `--lang {en,ru}` sets the interface language. In the TUI, use `/lang en|ru` or **Ctrl+T** to switch without restarting.
* `--reply {auto,en,ru}` sets the reply language. `auto` (the default) tells the model to answer in the same language as the user's message; `en` and `ru` force a specific language. Use `/reply` in the TUI to change it during a session.
* The system prompt itself stays in English; only its final language instruction changes. UI strings live in `daneel/i18n.py`.

## 🎨 Themes

Textual themes control the whole palette (chat log, input, panels, hint bar). Two custom themes ship with the project — `daneel` (dark, default) and `daneel-light` — and all built-in Textual themes are available too (`nord`, `dracula`, `gruvbox`, `catppuccin-*`, `solarized-*`, `rose-pine*` and others).

```bash
uv run daneel --theme dracula
DANEEL_THEME=nord daneel
```

In the TUI, run `/theme <name>` to switch instantly or `/theme` to list available themes. Unknown names fall back to the default.

The terminal font is controlled by your terminal emulator, not by the application. A monospace font with good Cyrillic coverage (for example Cascadia Code or JetBrains Mono) is recommended.

## 🧰 Tool confirmation

No tools are enabled by default. When the model requests a tool call, the active interface asks before running it:

* **CLI:** `Allow tool <name> with <arguments>? [Y/n]` — Enter (or `y`/`yes`/`да`) approves; `n`/`no`/`нет` denies. A denial is printed as a system message and the tool is not executed.
* **TUI:** a modal dialog shows the tool name and arguments. Enter confirms the focused button (Allow by default), Tab switches to Deny, and Esc or `n` denies. Denials appear as a note in the chat log.

A confirmation callback supplied by a caller always takes precedence over the interface default. The full design and its tickets live in `.scratch/tool-confirmation/`.

## 📋 Copying chat

Right-click text selected in the chat log to copy just that fragment. Right-click the input field to paste text at the cursor: the system clipboard is used when available, otherwise Daneel's own clipboard is used silently. On Linux, system clipboard access needs `xclip`/`xsel` (X11) or `wl-copy`/`wl-paste` (Wayland); headless and SSH sessions fall back to the in-app clipboard. `/copy` copies the whole visible transcript (messages, errors, and system notes), while `/copy last` copies only the latest agent answer. Feedback is localized and shown as a short notification in the top-right corner that disappears after two seconds; if nothing is selected or the chat is empty, a warning notification is shown instead. `/help` lists both commands.

Copying uses the terminal clipboard protocol (OSC52), which works in most terminals but not in all of them.

## 💾 Session history

Every completed exchange is saved automatically to a local SQLite database, so the context survives `Ctrl+C`.

* `/sessions` — open a right-hand sidebar with recent sessions; click one or press Enter to load it.
* `/load <id>` — textual variant of the same action.
* `/new` — start a fresh session.
* The sidebar also has a Delete button with a confirmation dialog. Close it with Escape or the Close button.

The database path comes from `DANEEL_SESSION_DB` or the platform-specific user data directory (`platformdirs`). The file is created automatically. Sessions keep the full message history, including tool calls, but only user and agent text is rendered in the chat.

## 🧩 Code layout

* `daneel/core.py` — core logic: streaming `/api/chat`, conversation history, the tool-call loop, and error handling.
* `daneel/clipboard.py` — system clipboard reads with an in-app fallback.
* `daneel/config.py` — environment-based settings with CLI overrides.
* `daneel/i18n.py` — interface strings, language resolution, and system prompt assembly.
* `daneel/storage.py` — SQLite session store; the only module that knows about the database.
* `daneel/theme.py` — custom Daneel themes, theme resolution, and registration.
* `daneel/cli.py` — plain-text confirmation prompt with injected input/output.
* `daneel/confirmation.py` — shared confirmation wiring and argument rendering used by both interfaces.
* `daneel/tools/` — tool contracts and registry; the extension point for agent operations. No tools are enabled by default, and confirmation is mandatory.
* `daneel/tui.py` — thin Textual layer: chat log, input field, localized messages.
* `main.py` — entry point; `--cli` selects the plain-text mode.
* `tests/` — core, config, i18n, theme, tools, storage, and TUI tests with a mock HTTP transport.

The agent logic is separated from the interface, so another UI or additional workers can be added without rewriting the core. Run the tests with:

```bash
uv run pytest
```

Coding conventions and design rules are documented in `CODING_STANDARDS.md`.

## 📦 Dependencies

All dependencies are declared in `pyproject.toml`; exact versions are pinned in `uv.lock`.

```bash
uv add <package>        # add a dependency
uv lock --upgrade       # update all packages to the latest compatible versions
uv sync                 # recreate the environment from the lock file
```

Commit `uv.lock` — it guarantees a reproducible environment.

## 💻 VS Code

Editor settings are local and ignored by git (`.vscode/`): paths to the interpreter differ between machines. Create `.vscode/settings.json` yourself, pointing Python/Pylance at the `.venv` interpreter:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true
}
```

On Windows use `${workspaceFolder}/.venv/Scripts/python.exe` instead. If Pylance still cannot find installed packages (`httpx`, `textual`), run **Python: Select Interpreter** → `.venv` and reload the window.

## 🤖 Agent skills (OpenCode)

A set of [skills](https://github.com/mattpocock/skills) for planning and development is installed **locally** and is not committed (`.agents/skills/` and `skills-lock.json` are in `.gitignore`). To set up a new environment, run:

```bash
npx --yes skills@latest add mattpocock/skills -a opencode \
  --skill setup-matt-pocock-skills --skill grill-with-docs --skill grilling \
  --skill domain-modeling --skill to-spec --skill to-tickets \
  --skill implement --skill tdd --skill codebase-design \
  --skill code-review --skill diagnosing-bugs -y
```

To update, re-run the full `add` command. `npx skills@latest update` only knows the skills recorded in the local `skills-lock.json`, which is not committed, so the full `add` is more reliable.

Typical feature workflow (skills are invoked via `@skill-id`):

1. `@setup-matt-pocock-skills` — once per repository; already done for this one.
2. `@grill-with-docs` — in-depth interview, glossary, and ADRs.
3. `@to-spec` — a spec in `.scratch/<feature>/spec.md`.
4. `@to-tickets` — tickets in `.scratch/<feature>/issues/`.
5. `@implement` — implementation with TDD and a final code review.

A worked example is `.scratch/tool-confirmation/`: a spec and two resolved tickets for the confirmation feature.

Specs and tickets, along with `AGENTS.md`, `docs/agents/*.md`, and any `GLOSSARY.md` or `docs/adr/` files that get created, are committed so the context and decisions travel with the code. See `docs/agents/issue-tracker.md` and `docs/agents/domain.md` for the conventions.
