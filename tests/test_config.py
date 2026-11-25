import json
from pathlib import Path

from daneel.config import Preferences, PreferencesStore, Settings


def test_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_env({})

    assert settings.base_url == "http://localhost:11434"
    assert settings.model == "qwen2.5:1.5b"
    assert settings.workspace == tmp_path
    assert settings.ui_language == "en"
    assert settings.reply_language == "auto"
    assert settings.theme == "daneel"


def test_environment_overrides() -> None:
    settings = Settings.from_env(
        {
            "OLLAMA_BASE_URL": "http://example:11434/",
            "DANEEL_MODEL": "llama3.2:3b",
            "DANEEL_WORKSPACE": "C:/work",
            "DANEEL_LANG": "ru",
            "DANEEL_REPLY": "ru",
            "DANEEL_THEME": "dracula",
        }
    )

    assert settings.base_url == "http://example:11434"
    assert settings.model == "llama3.2:3b"
    assert settings.workspace == Path("C:/work")
    assert settings.ui_language == "ru"
    assert settings.reply_language == "ru"
    assert settings.theme == "dracula"


def test_cli_values_override_environment() -> None:
    settings = Settings.from_env(
        {"DANEEL_LANG": "ru", "DANEEL_REPLY": "ru", "DANEEL_THEME": "dracula"}
    )

    overridden = settings.with_overrides(
        ui_language="en", reply_language="auto", theme="nord"
    )

    assert overridden.ui_language == "en"
    assert overridden.reply_language == "auto"
    assert overridden.theme == "nord"
    assert settings.ui_language == "ru"
    assert settings.theme == "dracula"


def test_preferences_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = PreferencesStore(path)

    store.update(ui_language="ru", reply_language="ru", theme="dracula")

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "ui_language": "ru",
        "reply_language": "ru",
        "theme": "dracula",
    }
    assert PreferencesStore.load(path).preferences == Preferences(
        ui_language="ru", reply_language="ru", theme="dracula"
    )


def test_preferences_ignore_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")

    assert PreferencesStore.load(path).preferences == Preferences()


def test_environment_overrides_saved_preferences() -> None:
    saved = Preferences(ui_language="ru", reply_language="ru", theme="dracula")

    settings = Settings.from_env({"DANEEL_LANG": "en"}, preferences=saved)

    assert settings.ui_language == "en"
    assert settings.reply_language == "ru"
    assert settings.theme == "dracula"
    assert saved == Preferences(ui_language="ru", reply_language="ru", theme="dracula")
