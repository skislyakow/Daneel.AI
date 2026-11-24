import pytest

from daneel.cli import cli_confirmation, install_cli_confirmation
from daneel.core import Conversation


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("", True), ("y", True), ("yes", True), ("да", True), ("n", False), ("нет", False)],
)
async def test_cli_confirmation_decides_from_answer(answer: str, expected: bool) -> None:
    prompts: list[str] = []
    output: list[str] = []

    def input_fn(prompt: str) -> str:
        prompts.append(prompt)
        return answer

    confirm = cli_confirmation(
        "en", input_fn=input_fn, output_fn=output.append
    )

    assert await confirm("echo", {"value": "hi"}) is expected
    assert "echo" in prompts[0]
    assert '"value": "hi"' in prompts[0]
    assert "[Y/n]" in prompts[0]


async def test_cli_confirmation_reports_denial_in_interface_language() -> None:
    output: list[str] = []
    confirm = cli_confirmation(
        "ru", input_fn=lambda _: "n", output_fn=output.append
    )

    assert await confirm("echo", {"value": "hi"}) is False
    assert any("отклонён" in line for line in output)


async def test_install_cli_confirmation_keeps_injected_callback() -> None:
    async def custom(name: str, arguments: dict) -> bool:
        return True

    conversation = Conversation(confirm=custom)
    install_cli_confirmation(conversation, "en")
    assert conversation.confirm is custom

    conversation = Conversation()
    install_cli_confirmation(conversation, "en")
    assert conversation.confirm is not None
