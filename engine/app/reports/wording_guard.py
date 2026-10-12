"""Report copy may never claim certification, audit or verification unless a real third-party
verification is recorded for the project (PRD F14 C, General Note 6)."""

from __future__ import annotations

import re

CLAIM_WORDS = re.compile(r"\b(certified|certification|audited|verified|assured)\b", re.IGNORECASE)


class WordingViolation(ValueError):
    pass


def check(texts: list[str], has_third_party_verification: bool) -> None:
    if has_third_party_verification:
        return
    for t in texts:
        m = CLAIM_WORDS.search(t or "")
        if m:
            raise WordingViolation(
                f'Report text claims "{m.group(0)}" but no third-party verification is recorded: "{t[:120]}"'
            )
