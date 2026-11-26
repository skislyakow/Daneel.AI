import json
import os
from pathlib import Path

from daneel.config import Preferences, PreferencesStore, Settings, load_env_file


def test_env_file_loads_without_overriding(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\nDANEEL_MODEL=qwen3.5:4b\nDANEEL_ENABLE_FS_TOOLS=1\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DANEEL_MODEL", raising=False)
    monkeypatch.delenv("DANEEL_ENABLE_FS_TOOLS", raising=False)
    monkeypatch.setenv("DANEEL_MODEL", "real-env-model")

    load_env_file(path)

    assert os.environ["DANEEL_MODEL"] == "real-env-model"
    assert os.environ["DANEEL_ENABLE_FS_TOOLS"] == "1"


def test_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_env({})

    assert settings.base_url == "http://localhost:11434"
    assert settings.model == "qwen3.5:4b"
    assert settings.workspace == tmp_path
    assert settings.ui_language == "en"
    assert settings.reply_language == "auto"
    assert settings.theme == "daneel"
    assert settings.enable_fs_tools is False
    assert settings.think is False
    assert settings.auto_route is True
    assert settings.num_ctx == 4096
    assert settings.num_predict == 512
    assert settings.temperature == 0.4
    assert settings.keep_alive == "30m"


def test_environment_overrides() -> None:
    settings = Settings.from_env(
        {
            "OLLAMA_BASE_URL": "http://example:11434/",
            "DANEEL_MODEL": "llama3.2:3b",
            "DANEEL_WORKSPACE": "C:/work",
            "DANEEL_LANG": "ru",
            "DANEEL_REPLY": "ru",
            "DANEEL_THEME": "dracula",
            "DANEEL_ENABLE_FS_TOOLS": "1",
            "DANEEL_THINK": "on",
            "DANEEL_ROUTER": "manual",
            "DANEEL_NUM_CTX": "8192",
        }
    )

    assert settings.base_url == "http://example:11434"
    assert settings.model == "llama3.2:3b"
    assert settings.workspace == Path("C:/work")
    assert settings.ui_language == "ru"
    assert settings.reply_language == "ru"
    assert settings.theme == "dracula"
    assert settings.enable_fs_tools is True
    assert settings.think is True
    assert settings.auto_route is False
    assert settings.num_ctx == 8192


def test_filesystem_tools_are_opt_in() -> None:
    assert Settings.from_env({"DANEEL_ENABLE_FS_TOOLS": "false"}).enable_fs_tools is False
    assert Settings.from_env({"DANEEL_ENABLE_FS_TOOLS": "yes"}).enable_fs_tools is True


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

    store.update(
        ui_language="ru",
        reply_language="ru",
        theme="dracula",
        model="qwen2.5:1.5b",
        think=True,
        auto_route=False,
    )

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "ui_language": "ru",
        "reply_language": "ru",
        "theme": "dracula",
        "model": "qwen2.5:1.5b",
        "think": True,
        "auto_route": False,
    }
    assert PreferencesStore.load(path).preferences == Preferences(
        ui_language="ru",
        reply_language="ru",
        theme="dracula",
        model="qwen2.5:1.5b",
        think=True,
        auto_route=False,
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
