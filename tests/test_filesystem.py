from pathlib import Path

from daneel.tools import ToolRegistry
from daneel.tools.filesystem import create_filesystem_tools


async def confirm(name: str, arguments: dict) -> bool:
    return True


def registry_for(workspace: Path) -> ToolRegistry:
    return ToolRegistry(create_filesystem_tools(workspace))


async def test_list_directory_shows_entries(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "sub").mkdir()

    result = await registry_for(tmp_path).call("list_directory", {}, confirm)

    assert "file notes.txt  5" in result
    assert "dir  sub" in result


async def test_read_file_returns_text(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("line one\nline two", encoding="utf-8")

    result = await registry_for(tmp_path).call(
        "read_file", {"path": "notes.txt"}, confirm
    )

    assert result == "line one\nline two"


async def test_paths_outside_workspace_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")

    outside_result = await registry_for(tmp_path).call(
        "read_file", {"path": str(outside)}, confirm
    )
    traversal_result = await registry_for(tmp_path).call(
        "read_file", {"path": "../outside-secret.txt"}, confirm
    )

    assert outside_result == f"Path outside workspace: {outside}"
    assert traversal_result == "Path outside workspace: ../outside-secret.txt"


async def test_large_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("0123456789", encoding="utf-8")
    registry = ToolRegistry(
        create_filesystem_tools(tmp_path, max_file_bytes=5)
    )

    result = await registry.call("read_file", {"path": "big.txt"}, confirm)

    assert result.startswith("File too large:")


async def test_tools_run_without_confirmation(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    tools = create_filesystem_tools(tmp_path)
    assert all(not tool.requires_confirmation for tool in tools)

    result = await ToolRegistry(tools).call("read_file", {"path": "notes.txt"})

    assert result == "hello"
