"""Categorization workflow (PRD Feature 6, step 3): unique inputs -> suggestion -> a person accepts.

Suggestions come only from the taxonomy subtree of the terminal the file was uploaded to.
Deterministic rules run first; the AI provider is consulted only where no rule matches.
Nothing is calculated until a person accepts.
"""

from __future__ import annotations

import json

from fastapi import HTTPException

from app.ai.provider import get_provider
from app.categorize.rules import match_rule
from app.db import Tx
from app.ingest.terminal import Terminal


def upsert_inputs(tx: Tx, project: dict, terminal: Terminal, inputs: dict[str, dict]) -> None:
    with tx.privileged():
        for key, display in inputs.items():
            tx.execute(
                """insert into public.categorizations (company_id, project_id, terminal_key, input_key, input_display)
                   values (%s, %s, %s, %s, %s::jsonb) on conflict (project_id, terminal_key, input_key) do nothing""",
                (project["company_id"], project["id"], terminal.key, key, json.dumps(display)),
            )


def leaf_options(tx: Tx, terminal: Terminal) -> list[dict]:
    """Leaf categories a file from this terminal may be mapped to (description paths only)."""
    if not terminal.taxonomy_root:
        return []
    return tx.all(
        """select id, path, name, display_path from ref.taxonomy_labels
           where is_leaf and (path = %s or path like %s) order by path""",
        (terminal.taxonomy_root, terminal.taxonomy_root + ".%"),
    )


def suggest(tx: Tx, project: dict, terminal: Terminal) -> int:
    """Fill suggestions for categorizations that have none yet. Returns how many were suggested."""
    pending = tx.all(
        """select id, input_key, input_display from public.categorizations
           where project_id = %s and terminal_key = %s and status = 'NEEDS'""",
        (project["id"], terminal.key),
    )
    if not pending:
        return 0
    with tx.privileged():
        rules = tx.all(
            """select r.match, r.priority, r.taxonomy_code, n.id as node_id
               from lib.categorization_rules r join lib.taxonomy_nodes n on n.code = r.taxonomy_code
               where r.terminal_key = %s""",
            (terminal.key,),
        )
    options = None
    provider = None
    done = 0
    for cat in pending:
        hit = match_rule(rules, cat["input_key"])
        node_id, by, note = (str(hit["node_id"]), "rule", None) if hit else (None, None, None)
        if node_id is None:
            if options is None:
                options = leaf_options(tx, terminal)
                provider = get_provider()
            if provider.available and options:
                suggestion = provider.suggest_category(
                    terminal.label,
                    cat["input_display"],
                    [{"id": str(o["id"]), "path": o["display_path"]} for o in options],
                )
                if suggestion and suggestion.node_id in {str(o["id"]) for o in options}:
                    node_id, by, note = suggestion.node_id, "ai", suggestion.reason
        if node_id:
            with tx.privileged():
                tx.execute(
                    """update public.categorizations set status = 'SUGGESTED', suggested_node_id = %s, suggested_by = %s,
                         suggested_at = now(), suggestion_note = %s where id = %s and status = 'NEEDS'""",
                    (node_id, by, note, cat["id"]),
                )
            done += 1
    return done


def assert_in_subtree(tx: Tx, terminal: Terminal, node_id: str) -> None:
    ok = tx.scalar(
        """select exists(select 1 from ref.taxonomy_labels where id = %s and is_leaf
                         and (path = %s or path like %s))""",
        (node_id, terminal.taxonomy_root, (terminal.taxonomy_root or "") + ".%"),
    )
    if not ok:
        raise HTTPException(
            422,
            f"That category is not part of {terminal.label}. A file uploaded here can only be "
            "mapped to this category's emission factors.",
        )


def accept(tx: Tx, cat_ids: list[str], node_ids: dict[str, str | None]) -> list[str]:
    """Mark categorizations accepted by the current user, recording who and when for every row."""
    accepted = []
    with tx.privileged():
        for cid in cat_ids:
            node = node_ids.get(cid)
            row = tx.one(
                """update public.categorizations
                   set status = 'ACCEPTED', accepted_node_id = coalesce(%s::uuid, suggested_node_id),
                       accepted_by = app.uid(), accepted_at = now()
                   where id = %s and coalesce(%s::uuid, suggested_node_id) is not null returning id""",
                (node, cid, node),
            )
            if row:
                accepted.append(str(row["id"]))
    return accepted
