"""Read-only filesystem tools confined to a configured workspace."""

from __future__ import annotations

from pathlib import Path

from .base import Arguments, FunctionTool

DEFAULT_MAX_ENTRIES = 200
DEFAULT_MAX_FILE_BYTES = 64_000

PATH_PROPERTY = {
    "type": "string",
    "description": "Path relative to the workspace root",
}


def _resolve_within(value: str, workspace: Path) -> Path | str:
    """Resolve a path and reject anything outside the workspace."""
    root = workspace.resolve()
    candidate = Path(value).expanduser()
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not resolved.is_relative_to(root):
        return f"Path outside workspace: {value}"
    return resolved


def create_filesystem_tools(
    workspace: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[FunctionTool]:
    """Build read-only tools rooted at the workspace directory."""

    async def list_directory(arguments: Arguments) -> str:
        raw = str(arguments.get("path", ".") or ".").strip() or "."
        target = _resolve_within(raw, workspace)
        if isinstance(target, str):
            return target
        if not target.exists():
            return f"Not found: {raw}"
        if not target.is_dir():
            return f"Not a directory: {raw}"

        try:
            entries = sorted(target.iterdir(), key=lambda path: path.name.lower())
        except OSError as exc:
            return f"Cannot list directory: {exc}"

        lines: list[str] = []
        for entry in entries[:max_entries]:
            try:
                size = entry.stat().st_size if entry.is_file() else 0
            except OSError:
                size = 0
            kind = "dir" if entry.is_dir() else "file"
            lines.append(f"{kind:4} {entry.name}  {size}")
        hidden = len(entries) - max_entries
        if hidden > 0:
            lines.append(f"... {hidden} more entries")
        return "\n".join(lines) if lines else "Directory is empty."

    async def read_file(arguments: Arguments) -> str:
        raw = str(arguments.get("path", "") or "").strip()
        if not raw:
            return "Invalid path: empty value"
        target = _resolve_within(raw, workspace)
        if isinstance(target, str):
            return target
        if not target.exists():
            return f"Not found: {raw}"
        if not target.is_file():
            return f"Not a file: {raw}"
        try:
            size = target.stat().st_size
        except OSError as exc:
            return f"Cannot stat file: {exc}"
        if size > max_file_bytes:
            return f"File too large: {size} bytes (limit {max_file_bytes})"
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"Cannot read file: {exc}"

    list_tool = FunctionTool(
        name="list_directory",
        description=(
            "List files and directories inside the configured workspace. "
            "Use for questions about what is in a directory."
        ),
        parameters={
            "type": "object",
            "properties": {"path": PATH_PROPERTY},
            "required": [],
        },
        runner=list_directory,
        requires_confirmation=False,
    )
    read_tool = FunctionTool(
        name="read_file",
        description=(
            "Read a UTF-8 text file from the configured workspace. "
            "Use for questions about the contents of a known file."
        ),
        parameters={
            "type": "object",
            "properties": {"path": PATH_PROPERTY},
            "required": ["path"],
        },
        runner=read_file,
        requires_confirmation=False,
    )
    return [list_tool, read_tool]
