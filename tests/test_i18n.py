from daneel.i18n import (
    STRINGS,
    build_system_prompt,
    resolve_reply_language,
    resolve_ui_language,
    t,
)


def test_locales_have_the_same_keys() -> None:
    assert set(STRINGS["en"]) == set(STRINGS["ru"])


def test_resolve_ui_language() -> None:
    assert resolve_ui_language() == "en"
    assert resolve_ui_language("ru") == "ru"
    assert resolve_ui_language(None, "RU") == "ru"
    assert resolve_ui_language("fr") == "en"


def test_resolve_reply_language() -> None:
    assert resolve_reply_language() == "auto"
    assert resolve_reply_language("ru") == "ru"
    assert resolve_reply_language("invalid") == "auto"


def test_build_system_prompt_appends_reply_instruction() -> None:
    assert build_system_prompt("auto").endswith(
        "Reply in the same language as the user's message."
    )
    assert build_system_prompt("en").endswith("Reply in English.")
    assert build_system_prompt("ru").endswith("Reply in Russian.")


def test_translation_substitutes_placeholders() -> None:
    assert t("en", "lang_changed", language="RU") == "Interface language: RU"
    assert (
        t("ru", "unknown_command", command="foo")
        == "Неизвестная команда: foo. Введите /help для списка."
    )
