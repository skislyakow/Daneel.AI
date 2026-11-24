"""Built-in and custom Textual themes for Daneel.AI."""

from __future__ import annotations

from textual.app import App
from textual.theme import BUILTIN_THEMES, Theme

DEFAULT_THEME = "daneel"

DANEEL_DARK = Theme(
    name="daneel",
    primary="#5AA9E6",
    secondary="#2E5E8C",
    warning="#E5B567",
    error="#E06C75",
    success="#7FBF7F",
    accent="#66D9EF",
    foreground="#DDE6EE",
    background="#11161C",
    surface="#171F27",
    panel="#1E2933",
    dark=True,
    variables={"footer-background": "#1E2933"},
)

DANEEL_LIGHT = Theme(
    name="daneel-light",
    primary="#1F6FA8",
    secondary="#3E6E96",
    warning="#9A6B00",
    error="#B23A48",
    success="#2F7A3E",
    accent="#007C91",
    foreground="#21313F",
    background="#F2F5F8",
    surface="#E5EBF1",
    panel="#D8E0E8",
    dark=False,
    variables={"footer-background": "#D8E0E8"},
)

CUSTOM_THEMES: dict[str, Theme] = {
    DANEEL_DARK.name: DANEEL_DARK,
    DANEEL_LIGHT.name: DANEEL_LIGHT,
}


def available_themes() -> list[str]:
    """Return all theme names that can be selected."""
    return sorted(set(BUILTIN_THEMES) | set(CUSTOM_THEMES))


def resolve_theme(argument: str | None = None, env: str | None = None) -> str:
    """Resolve a theme name from a CLI argument, env var, or default."""
    name = (argument or env or DEFAULT_THEME).lower()
    return name if name in available_themes() else DEFAULT_THEME


def register_themes(app: App[None]) -> None:
    """Register Daneel's custom themes with the application."""
    for theme in CUSTOM_THEMES.values():
        app.register_theme(theme)
