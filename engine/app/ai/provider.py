"""AIProvider abstraction (PRD Features 5 and 6).

AI may only *extract* candidate values from a bill or *suggest* a category. Every output is shown
to a person for confirmation; nothing an AI returns is saved as data or used in a calculation
without that confirmation, and AI never computes an emissions number.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


@dataclass(frozen=True)
class CategorySuggestion:
    node_id: str
    reason: str | None


@dataclass(frozen=True)
class BillExtraction:
    document_type: str | None  # e.g. "electricity_bill", or None if not recognised
    fields: dict[str, str | None]  # candidate values, as text, keyed by the terminal's bill fields
    confidence: dict[str, str]  # field -> high | medium | low
    notes: str | None


class AIProvider(Protocol):
    name: str
    model: str | None
    available: bool

    def suggest_category(
        self, terminal_label: str, inputs: dict[str, str], options: list[dict[str, str]]
    ) -> CategorySuggestion | None: ...

    def extract_bill(self, data: bytes, media_type: str, fields: dict[str, str]) -> BillExtraction: ...


class NullProvider:
    """Used when no AI key is configured: rules-only suggestions and a blank manual bill form."""

    name = "none"
    model = None
    available = False

    def suggest_category(self, terminal_label, inputs, options):
        return None

    def extract_bill(self, data, media_type, fields):
        return BillExtraction(
            None, dict.fromkeys(fields), {}, "AI extraction is not configured; enter the values manually."
        )


@lru_cache
def get_provider() -> AIProvider:
    s = get_settings()
    if s.ai_provider == "anthropic" and s.anthropic_api_key:
        from app.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(s.anthropic_api_key, s.ai_model)
    return NullProvider()
