"""Generic applicability evaluator for regulatory requirements (PRD F14 A).

Conditions are data, e.g.
  {"all": [{"field": "facility.environmental_classification", "op": "in", "value": ["ORANGE", "RED"]},
           {"field": "facility.employee_count", "op": "gte", "value": 50}]}
Combinators: all, any, not. Operators: eq, ne, in, not_in, gt, gte, lt, lte, exists.
Adding or changing a rule is a data change; no code or deployment is needed.
"""

from __future__ import annotations

from typing import Any

OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "exists": lambda a, b: (a is not None) == bool(b),
}


class ConditionError(ValueError):
    pass


def _get(context: dict[str, Any], field: str) -> Any:
    obj: Any = context
    for part in field.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def evaluate(cond: dict, context: dict[str, Any]) -> tuple[bool, list[str]]:
    """Returns (applies, reasons). Reasons describe the leaf conditions that held."""
    if "all" in cond:
        results = [evaluate(c, context) for c in cond["all"]]
        ok = all(r[0] for r in results)
        return ok, [x for r in results for x in r[1]] if ok else []
    if "any" in cond:
        hits = [r for r in (evaluate(c, context) for c in cond["any"]) if r[0]]
        return bool(hits), [x for r in hits for x in r[1]]
    if "not" in cond:
        ok, _ = evaluate(cond["not"], context)
        return not ok, ["not (" + str(cond["not"]) + ")"] if not ok else []
    if "field" in cond:
        op = cond.get("op", "eq")
        if op not in OPS:
            raise ConditionError(f"Unknown operator {op}")
        actual = _get(context, cond["field"])
        ok = bool(OPS[op](actual, cond.get("value")))
        return ok, [f"{cond['field']} = {actual}"] if ok else []
    raise ConditionError(f"Invalid condition: {cond}")


def fields(cond: dict) -> set[str]:
    if "all" in cond or "any" in cond:
        return {f for c in cond.get("all", cond.get("any", [])) for f in fields(c)}
    if "not" in cond:
        return fields(cond["not"])
    return {cond["field"]} if "field" in cond else set()


def validate(cond: dict) -> None:
    """Raise ConditionError for malformed conditions (used before saving a requirement)."""
    evaluate(cond, {})
