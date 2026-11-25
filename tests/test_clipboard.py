import pyperclip
import pytest

from daneel.clipboard import read_text


def test_read_text_returns_system_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pyperclip, "paste", lambda: "from system")

    assert read_text("from app") == "from system"


def test_read_text_falls_back_when_system_clipboard_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> str:
        raise pyperclip.PyperclipException("no clipboard utility")

    monkeypatch.setattr(pyperclip, "paste", unavailable)

    assert read_text("from app") == "from app"


def test_read_text_falls_back_when_system_clipboard_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    assert read_text("from app") == "from app"
