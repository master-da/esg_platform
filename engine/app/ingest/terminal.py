"""Upload-terminal configuration (ref.terminals.config). One terminal per scope/category (PRD F5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def norm(text: Any) -> str:
    """Normalise headers and categorical values: trimmed, single-spaced, case-folded."""
    return " ".join(str(text).replace("*", " ").split()).casefold()


@dataclass(frozen=True)
class Column:
    key: str
    header: str
    type: str  # facility | date | decimal | integer | enum | unit | text
    required: bool = False
    options: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    role: str | None = None  # quantity | unit | data_basis


@dataclass(frozen=True)
class Terminal:
    key: str
    module: str
    scope: int | None
    category_no: str | None
    name: str
    description: str
    excludes: str | None
    instructions: str | None
    taxonomy_root: str | None
    accepts_bills: bool
    enabled: bool
    disabled_reason: str | None
    template_version: str
    activity_type: str
    columns: tuple[Column, ...]
    categorization_keys: tuple[str, ...]
    quality_grades: dict[str, str]
    canonical_units: dict[str, str]
    rules: tuple[dict, ...]
    default_grade: str | None = None
    bill_fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict) -> Terminal:
        cfg = row["config"]
        cols = tuple(
            Column(
                key=c["key"],
                header=c["header"],
                type=c["type"],
                required=c.get("required", False),
                options=tuple(c.get("options", [])),
                min=c.get("min"),
                max=c.get("max"),
                role=c.get("role"),
            )
            for c in cfg["columns"]
        )
        return cls(
            key=row["key"],
            module=row["module"],
            scope=row["scope"],
            category_no=row["category_no"],
            name=row["name"],
            description=row["description"],
            excludes=row.get("excludes"),
            instructions=row.get("instructions"),
            taxonomy_root=row.get("taxonomy_root"),
            accepts_bills=row["accepts_bills"],
            enabled=row["enabled"],
            disabled_reason=row.get("disabled_reason"),
            template_version=row["template_version"],
            activity_type=cfg["activity_type"],
            columns=cols,
            categorization_keys=tuple(cfg.get("categorization_keys", [])),
            quality_grades=cfg.get("quality_grades", {}),
            canonical_units=cfg.get("canonical_units", {}),
            rules=tuple(cfg.get("rules", [])),
            default_grade=cfg.get("default_grade"),
            bill_fields=cfg.get("bill_fields", {}),
        )

    def column(self, key: str) -> Column | None:
        return next((c for c in self.columns if c.key == key), None)

    def role(self, role: str) -> Column | None:
        return next((c for c in self.columns if c.role == role), None)

    @property
    def label(self) -> str:
        scope = f"Scope {self.scope} " if self.scope else ""
        return f"{scope}{self.name}".strip()


def load_terminals(tx) -> dict[str, Terminal]:
    return {r["key"]: Terminal.from_row(r) for r in tx.all("select * from ref.terminals order by sort")}


def load_terminal(tx, key: str) -> Terminal | None:
    row = tx.one("select * from ref.terminals where key = %s", (key,))
    return Terminal.from_row(row) if row else None
