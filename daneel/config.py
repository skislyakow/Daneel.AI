"""Runtime configuration read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import (
    ReplyLanguage,
    UILanguage,
    resolve_reply_language,
    resolve_ui_language,
)
from .theme import DEFAULT_THEME, resolve_theme

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"


@dataclass(slots=True)
class Settings:
    """Effective settings for a Daneel.AI session."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    workspace: Path = field(default_factory=Path.cwd)
    ui_language: UILanguage = "en"
    reply_language: ReplyLanguage = "auto"
    theme: str = DEFAULT_THEME

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from the current environment or a supplied mapping."""
        env = environ if environ is not None else os.environ
        return cls(
            base_url=env.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=env.get("DANEEL_MODEL", DEFAULT_MODEL),
            workspace=Path(env.get("DANEEL_WORKSPACE", str(Path.cwd()))).expanduser(),
            ui_language=resolve_ui_language(None, env.get("DANEEL_LANG")),
            reply_language=resolve_reply_language(env.get("DANEEL_REPLY")),
            theme=resolve_theme(None, env.get("DANEEL_THEME")),
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
        )
