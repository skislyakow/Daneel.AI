from daneel.commands import COMMANDS, matching_commands


def test_matching_commands_filters_by_prefix() -> None:
    assert [command.name for command in matching_commands("/")] == [
        command.name for command in COMMANDS
    ]
    assert [command.name for command in matching_commands("/s")] == ["sessions"]
    assert matching_commands("/unknown") == []


def test_command_insert_text_omits_placeholders() -> None:
    theme = next(command for command in COMMANDS if command.name == "theme")

    assert theme.usage == "/theme <name>"
    assert theme.insert_text == "/theme "


def test_commands_declare_argument_menus() -> None:
    commands = {command.name: command for command in COMMANDS}

    assert [choice.value for choice in commands["lang"].choices] == ["en", "ru"]
    assert [choice.value for choice in commands["reply"].choices] == [
        "auto",
        "en",
        "ru",
    ]
    assert [choice.value for choice in commands["copy"].choices] == ["all", "last"]
    assert commands["theme"].choices == "themes"
    assert commands["sessions"].choices == "sessions"
    assert commands["new"].choices is None
    assert "load" not in commands
