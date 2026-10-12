"""Categorization inputs and deterministic suggestion rules (PRD Feature 6, "Matching data to a code")."""

from __future__ import annotations

from typing import Any

from app.ingest.terminal import Terminal, norm


def input_key(terminal: Terminal, values: dict[str, Any]) -> str:
    """Stable key for one unique combination of the terminal's categorization columns."""
    return "|".join(f"{k}={norm(values.get(k) or '')}" for k in terminal.categorization_keys)


def input_display(terminal: Terminal, values: dict[str, Any]) -> dict[str, str]:
    out = {}
    for k in terminal.categorization_keys:
        col = terminal.column(k)
        out[col.header if col else k] = "" if values.get(k) is None else str(values[k])
    return out


def match_rule(rules: list[dict], key: str) -> dict | None:
    """Rules match when every field in rule.match equals the normalised input value.
    Highest priority wins; ties go to the most specific rule (more fields), then stable order."""
    parts = dict(p.split("=", 1) for p in key.split("|") if "=" in p)
    hits = [r for r in rules if all(parts.get(k) == norm(v) for k, v in r["match"].items())]
    if not hits:
        return None
    return sorted(hits, key=lambda r: (-r["priority"], -len(r["match"]), str(r["match"])))[0]
