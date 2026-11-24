import pytest

from daneel.tools import FunctionTool, ToolDenied, ToolNotFoundError, ToolRegistry


def echo_tool() -> FunctionTool:
    async def runner(arguments: dict) -> str:
        return f"echo:{arguments['value']}"

    return FunctionTool(
        name="echo",
        description="Echo a value back",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        runner=runner,
    )


def test_registry_builds_ollama_schema() -> None:
    schema = ToolRegistry([echo_tool()]).as_schema()

    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == "echo"
    assert schema[0]["function"]["parameters"]["required"] == ["value"]


async def test_confirmation_is_mandatory() -> None:
    registry = ToolRegistry([echo_tool()])

    with pytest.raises(ToolDenied):
        await registry.call("echo", {"value": "hi"})


async def test_confirmed_tool_runs() -> None:
    seen: list[tuple[str, dict]] = []

    async def confirm(name: str, arguments: dict) -> bool:
        seen.append((name, arguments))
        return True

    result = await ToolRegistry([echo_tool()]).call("echo", {"value": "hi"}, confirm)

    assert result == "echo:hi"
    assert seen == [("echo", {"value": "hi"})]


async def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(ToolNotFoundError):
        await ToolRegistry().call("missing", {}, None)
