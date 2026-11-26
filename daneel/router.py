"""Heuristic routing between a light and a heavy chat model."""

from __future__ import annotations

from dataclasses import dataclass

from .config import HEAVY_MODEL, LIGHT_MODEL

TOOL_MARKERS = (
    "погод",
    "weather",
    "файл",
    "file",
    "прочитай",
    "read ",
    "список",
    "directory",
    "папк",
    "каталог",
)
COMPLEX_MARKERS = (
    "проанализируй",
    "analyze",
    "сравни",
    "compare",
    "подробно",
    "in detail",
    "объясни",
    "explain",
    "почему",
    "why",
    "архитектур",
    "architecture",
    "рефактор",
    "refactor",
)
CODE_MARKERS = ("```", "def ", "class ", "import ", "select ")
COMPLEX_LENGTH = 240


@dataclass(frozen=True, slots=True)
class ModelRouter:
    """Choose a model from the user's message without an extra LLM call."""

    light_model: str = LIGHT_MODEL
    heavy_model: str = HEAVY_MODEL

    def choose(self, text: str) -> str:
        """Return the heavy model for hard requests, the light one otherwise."""
        value = text.lower()
        if any(marker in value for marker in TOOL_MARKERS):
            return self.heavy_model
        if any(marker in value for marker in COMPLEX_MARKERS):
            return self.heavy_model
        if any(marker in value for marker in CODE_MARKERS):
            return self.heavy_model
        if len(text) >= COMPLEX_LENGTH:
            return self.heavy_model
        return self.light_model
