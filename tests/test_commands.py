from daneel.commands import COMMANDS, matching_commands


def test_matching_commands_filters_by_prefix() -> None:
    assert [command.name for command in matching_commands("/")] == [
        command.name for command in COMMANDS
    ]
    assert [command.name for command in matching_commands("/s")] == ["sessions"]
    assert matching_commands("/unknown") == []


def test_command_insert_text_omits_placeholders() -> None:
    load = next(command for command in COMMANDS if command.name == "load")

    assert load.usage == "/load <id>"
    assert load.insert_text == "/load "
