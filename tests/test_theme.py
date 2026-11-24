from textual.app import App

from daneel.theme import (
    CUSTOM_THEMES,
    DEFAULT_THEME,
    available_themes,
    register_themes,
    resolve_theme,
)


def test_resolve_theme_precedence() -> None:
    assert resolve_theme() == DEFAULT_THEME
    assert resolve_theme(None, "dracula") == "dracula"
    assert resolve_theme("nord", "dracula") == "nord"
    assert resolve_theme("missing") == DEFAULT_THEME


def test_available_themes_include_custom_and_builtin() -> None:
    names = available_themes()

    assert "daneel" in names
    assert "daneel-light" in names
    assert "dracula" in names
    assert "nord" in names


def test_register_themes() -> None:
    app = App()

    register_themes(app)

    for name in CUSTOM_THEMES:
        assert app.get_theme(name) is not None
