"""Turn a Classification into a triage bucket and a priority score.

The model proposes labels; these rules decide what the analyst sees first.
"""

import math

from harmwatch.schema import Classification

HARMFUL = "harmful"
POTENTIAL = "potentially_harmful"
NOT_HARMFUL = "not_harmful"
ESCALATE = "escalate"  # child + sexual element: never displayed, routed to legal

BUCKET_RANK = {ESCALATE: 3, HARMFUL: 2, POTENTIAL: 1, NOT_HARMFUL: 0}


def triage(c: Classification) -> str:
    potential = max(0, min(3, c.harm_potential))
    if "child" in c.victims and (c.harm_types or potential > 0):
        return ESCALATE
    if potential >= 2 and c.confidence != "low" and c.harm_types:
        return HARMFUL
    if c.harm_types or potential >= 1 or c.confidence == "low":
        return POTENTIAL
    return NOT_HARMFUL


def priority(c: Classification, views: int | None = None) -> float:
    """Higher = review sooner. Bucket dominates, then severity, then reach."""
    reach = math.log10((views or 0) + 1)  # 0..~7
    return BUCKET_RANK[triage(c)] * 100 + max(0, min(3, c.harm_potential)) * 10 + reach
