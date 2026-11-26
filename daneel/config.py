"""Runtime configuration read from environment variables."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from .i18n import (
    ReplyLanguage,
    UILanguage,
    resolve_reply_language,
    resolve_ui_language,
)
from .theme import DEFAULT_THEME, resolve_theme

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
DB_FILENAME = "sessions.sqlite3"
PREFERENCES_FILENAME = "settings.json"


def default_db_path() -> Path:
    """Return the platform-specific location of the session database."""
    return Path(user_data_dir("daneel", appauthor="Daneel.AI")) / DB_FILENAME


def default_preferences_path() -> Path:
    """Return the platform-specific location of the preferences file."""
    return Path(user_config_dir("daneel", appauthor="Daneel.AI")) / PREFERENCES_FILENAME


def project_env_path() -> Path:
    """Return the .env file next to the project's pyproject.toml."""
    return Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs into os.environ without overriding real variables."""
    target = path or project_env_path()
    if not target.exists():
        return
    for line in target.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, _, value = entry.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(slots=True)
class Preferences:
    """User preferences changed from the interface and kept between runs."""

    ui_language: UILanguage = "en"
    reply_language: ReplyLanguage = "auto"
    theme: str = DEFAULT_THEME

    @classmethod
    def from_dict(cls, data: object) -> Preferences:
        """Build preferences from stored JSON, ignoring unknown values."""
        if not isinstance(data, dict):
            return cls()
        ui = data.get("ui_language")
        reply = data.get("reply_language")
        theme = data.get("theme")
        return cls(
            ui_language=resolve_ui_language(ui if isinstance(ui, str) else None),
            reply_language=resolve_reply_language(
                reply if isinstance(reply, str) else None
            ),
            theme=resolve_theme(theme if isinstance(theme, str) else None),
        )

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation."""
        return {
            "ui_language": self.ui_language,
            "reply_language": self.reply_language,
            "theme": self.theme,
        }

    def with_environment(self, environ: Mapping[str, str]) -> Preferences:
        """Apply explicitly set environment variables over stored values."""
        return Preferences(
            ui_language=(
                resolve_ui_language(environ.get("DANEEL_LANG"))
                if "DANEEL_LANG" in environ
                else self.ui_language
            ),
            reply_language=(
                resolve_reply_language(environ.get("DANEEL_REPLY"))
                if "DANEEL_REPLY" in environ
                else self.reply_language
            ),
            theme=(
                resolve_theme(environ.get("DANEEL_THEME"))
                if "DANEEL_THEME" in environ
                else self.theme
            ),
        )

    def with_overrides(
        self,
        ui_language: UILanguage | None = None,
        reply_language: ReplyLanguage | None = None,
        theme: str | None = None,
    ) -> Preferences:
        """Apply CLI or interface values over stored values."""
        return Preferences(
            ui_language=ui_language or self.ui_language,
            reply_language=reply_language or self.reply_language,
            theme=resolve_theme(theme, self.theme) if theme else self.theme,
        )


@dataclass(slots=True)
class PreferencesStore:
    """Load and atomically persist user preferences."""

    path: Path
    preferences: Preferences = field(default_factory=Preferences)

    @classmethod
    def load(cls, path: Path | None = None) -> PreferencesStore:
        """Read preferences from disk, falling back to defaults if unreadable."""
        target = path or default_preferences_path()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(target)
        return cls(target, Preferences.from_dict(data))

    def update(self, **changes: str) -> None:
        """Merge changes and write them to disk."""
        self.preferences = self.preferences.with_overrides(**changes)
        self.save()

    def save(self) -> None:
        """Write preferences through a temporary file to avoid partial writes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(self.preferences.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


@dataclass(slots=True)
class Settings:
    """Effective settings for a Daneel.AI session."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    workspace: Path = field(default_factory=Path.cwd)
    ui_language: UILanguage = "en"
    reply_language: ReplyLanguage = "auto"
    theme: str = DEFAULT_THEME
    session_db: Path = field(default_factory=default_db_path)
    enable_fs_tools: bool = False

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        preferences: Preferences | None = None,
    ) -> Settings:
        """Build settings from environment and optional saved preferences."""
        env = environ if environ is not None else os.environ
        prefs = (preferences or Preferences()).with_environment(env)
        return cls(
            base_url=env.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=env.get("DANEEL_MODEL", DEFAULT_MODEL),
            workspace=Path(env.get("DANEEL_WORKSPACE", str(Path.cwd()))).expanduser(),
            ui_language=prefs.ui_language,
            reply_language=prefs.reply_language,
            theme=prefs.theme,
            session_db=Path(
                env.get("DANEEL_SESSION_DB", str(default_db_path()))
            ).expanduser(),
            enable_fs_tools=env.get("DANEEL_ENABLE_FS_TOOLS", "").lower()
            in {"1", "true", "yes"},
        )

    def with_overrides(
        self,
        ui_language: UILanguage | None = None,
        reply_language: ReplyLanguage | None = None,
        theme: str | None = None,
    ) -> Settings:
        """Return a copy with CLI values overriding the environment."""
        return Settings(
            base_url=self.base_url,
            model=self.model,
            workspace=self.workspace,
            ui_language=ui_language or self.ui_language,
            reply_language=reply_language or self.reply_language,
            theme=resolve_theme(theme, self.theme) if theme else self.theme,
            session_db=self.session_db,
            enable_fs_tools=self.enable_fs_tools,
        )
