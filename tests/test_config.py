from pathlib import Path

from daneel.config import Settings


def test_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings.from_env({})

    assert settings.base_url == "http://localhost:11434"
    assert settings.model == "qwen2.5:1.5b"
    assert settings.workspace == tmp_path
    assert settings.ui_language == "en"
    assert settings.reply_language == "auto"


def test_environment_overrides() -> None:
    settings = Settings.from_env(
        {
            "OLLAMA_BASE_URL": "http://example:11434/",
            "DANEEL_MODEL": "llama3.2:3b",
            "DANEEL_WORKSPACE": "C:/work",
            "DANEEL_LANG": "ru",
            "DANEEL_REPLY": "ru",
        }
    )

    assert settings.base_url == "http://example:11434"
    assert settings.model == "llama3.2:3b"
    assert settings.workspace == Path("C:/work")
    assert settings.ui_language == "ru"
    assert settings.reply_language == "ru"


def test_cli_values_override_environment() -> None:
    settings = Settings.from_env({"DANEEL_LANG": "ru", "DANEEL_REPLY": "ru"})

    overridden = settings.with_overrides(ui_language="en", reply_language="auto")

    assert overridden.ui_language == "en"
    assert overridden.reply_language == "auto"
    assert settings.ui_language == "ru"
