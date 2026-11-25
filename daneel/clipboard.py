"""Cross-platform clipboard reads with an in-app fallback."""

from __future__ import annotations

import pyperclip


def read_text(fallback: str) -> str:
    """Read the system clipboard, falling back to Daneel's own clipboard.

    Linux needs an external utility (xclip, xsel or wl-copy) for system
    clipboard access. If it is unavailable, or no system text is present, the
    text copied earlier inside the app is used instead.
    """
    try:
        text = pyperclip.paste()
    except pyperclip.PyperclipException:
        return fallback
    return text or fallback
